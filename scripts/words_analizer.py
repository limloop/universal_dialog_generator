#!/usr/bin/env python3
"""
Config Analyzer for JSON Generation Templates
Checks if all placeholder variables in templates have corresponding word lists.
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Set, Dict, List, Tuple


def extract_placeholders(template: str) -> Set[str]:
    """
    Extract all placeholders in format ${variable_name} from a template string.
    """
    # Pattern matches ${word} where word can contain letters, numbers, underscores
    pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
    return set(re.findall(pattern, template))


def analyze_config(config_path: str) -> Tuple[Dict[str, Set[str]], Set[str], Set[str]]:
    """
    Analyze config file and return:
    - templates_with_vars: dict of template index -> set of variables
    - all_template_vars: set of all variables found in templates
    - words_keys: set of keys in prompt_templates.words
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    templates = config['prompt_templates']['templates']
    words_keys = set(config['prompt_templates']['words'].keys())
    
    templates_with_vars = {}
    all_template_vars = set()
    
    print(f"\n📊 Analyzing {len(templates)} templates...\n")
    
    for i, template in enumerate(templates):
        vars_in_template = extract_placeholders(template)
        templates_with_vars[i] = vars_in_template
        all_template_vars.update(vars_in_template)
        
        # Print template analysis
        print(f"Template #{i}:")
        print(f"  📝 {template[:80]}..." if len(template) > 80 else f"  📝 {template}")
        print(f"  🔍 Found {len(vars_in_template)} placeholders: {sorted(vars_in_template)}")
        print()
    
    return templates_with_vars, all_template_vars, words_keys


def check_coverage(all_template_vars: Set[str], words_keys: Set[str]) -> Dict:
    """
    Check coverage of template variables in words dictionary.
    Returns dict with analysis results.
    """
    missing_keys = all_template_vars - words_keys
    extra_keys = words_keys - all_template_vars
    covered_keys = all_template_vars & words_keys
    
    return {
        'missing': missing_keys,
        'extra': extra_keys,
        'covered': covered_keys,
        'total_template_vars': len(all_template_vars),
        'total_words_keys': len(words_keys),
        'coverage_percent': round(len(covered_keys) / len(all_template_vars) * 100, 2) if all_template_vars else 0
    }


def generate_report(config_path: str, 
                   templates_with_vars: Dict[int, Set[str]], 
                   coverage: Dict) -> None:
    """
    Generate detailed report of the analysis.
    """
    print("=" * 80)
    print("🔍 CONFIG ANALYSIS REPORT")
    print("=" * 80)
    
    # Summary statistics
    print(f"\n📈 SUMMARY:")
    print(f"  • Total templates: {len(templates_with_vars)}")
    print(f"  • Unique placeholders in templates: {coverage['total_template_vars']}")
    print(f"  • Word lists in config: {coverage['total_words_keys']}")
    print(f"  • Coverage: {coverage['coverage_percent']}%")
    
    # Missing keys
    if coverage['missing']:
        print(f"\n❌ MISSING KEYS ({len(coverage['missing'])}):")
        print(f"   These variables are used in templates but don't have word lists:")
        for key in sorted(coverage['missing']):
            # Find which templates use this key
            using_templates = []
            for i, vars_set in templates_with_vars.items():
                if key in vars_set:
                    using_templates.append(f"#{i}")
            print(f"  • {key} (used in templates: {', '.join(using_templates)})")
    else:
        print(f"\n✅ No missing keys! All template variables have word lists.")
    
    # Extra keys
    if coverage['extra']:
        print(f"\n⚠️  EXTRA KEYS ({len(coverage['extra'])}):")
        print(f"   These word lists exist but aren't used in any template:")
        for key in sorted(coverage['extra'])[:20]:  # Limit to 20 to avoid spam
            print(f"  • {key}")
        if len(coverage['extra']) > 20:
            print(f"  • ... and {len(coverage['extra']) - 20} more")
    else:
        print(f"\n✅ No extra keys - all word lists are used.")
    
    # Coverage by usage
    print(f"\n📊 COVERAGE DETAILS:")
    print(f"  • Covered: {len(coverage['covered'])} keys")
    print(f"  • Missing: {len(coverage['missing'])} keys")
    print(f"  • Extra: {len(coverage['extra'])} keys")
    
    # Template coverage
    print(f"\n📝 TEMPLATE COVERAGE:")
    for i, vars_set in sorted(templates_with_vars.items()):
        missing_in_template = vars_set & coverage['missing']
        if missing_in_template:
            status = "❌ INCOMPLETE"
            details = f"missing: {sorted(missing_in_template)}"
        else:
            status = "✅ COMPLETE"
            details = "all variables covered"
        print(f"  Template #{i}: {status} ({len(vars_set)} vars, {details})")


def generate_missing_keys_json(coverage: Dict) -> Dict:
    """
    Generate a JSON structure with missing keys and example entries.
    Useful for adding to config.
    """
    if not coverage['missing']:
        return {"message": "No missing keys!"}
    
    missing_structure = {}
    for key in sorted(coverage['missing']):
        # Generate example entries based on key name
        if key.startswith(('protagonist_', 'character_', 'secondary_')):
            missing_structure[key] = ["значение 1", "значение 2", "значение 3"]
        elif key.endswith(('_type', '_trait', '_age', '_job')):
            missing_structure[key] = ["тип 1", "тип 2", "тип 3"]
        elif key.endswith(('_location', '_place', '_habitat')):
            missing_structure[key] = ["локация 1", "локация 2", "локация 3"]
        elif key.endswith(('_description', '_story', '_message')):
            missing_structure[key] = ["описание 1", "описание 2", "описание 3"]
        elif key.endswith(('_reaction', '_emotion', '_feeling')):
            missing_structure[key] = ["реакция 1", "реакция 2", "реакция 3"]
        else:
            missing_structure[key] = ["значение 1", "значение 2", "значение 3"]
    
    return missing_structure


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze JSON config for missing word lists')
    parser.add_argument('config_file', help='Path to config JSON file')
    parser.add_argument('--json', action='store_true', help='Output missing keys as JSON')
    parser.add_argument('--fix', action='store_true', help='Generate missing keys structure for fixing')
    
    args = parser.parse_args()
    
    config_path = Path(args.config_file)
    if not config_path.exists():
        print(f"❌ Error: File {config_path} not found!")
        return 1
    
    try:
        templates_with_vars, all_template_vars, words_keys = analyze_config(args.config_file)
        coverage = check_coverage(all_template_vars, words_keys)
        
        if args.json:
            # Output just the missing keys as JSON
            result = {
                "missing_keys": sorted(coverage['missing']),
                "extra_keys": sorted(coverage['extra']),
                "total_missing": len(coverage['missing']),
                "coverage_percent": coverage['coverage_percent']
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif args.fix:
            # Generate JSON structure for missing keys (to add to config)
            missing_json = generate_missing_keys_json(coverage)
            print("\n📋 MISSING KEYS STRUCTURE (copy this to your config):")
            print(json.dumps(missing_json, indent=2, ensure_ascii=False))
        
        else:
            # Full report
            generate_report(args.config_file, templates_with_vars, coverage)
            
            # Suggestions for next steps
            print("\n💡 NEXT STEPS:")
            if coverage['missing']:
                print("  • Add missing word lists to your config")
                print(f"  • Run with --fix to generate JSON structure for missing keys")
            if coverage['extra']:
                print("  • Consider removing unused word lists or using them in new templates")
            print("  • Run with --json to get machine-readable output")
        
        return 0
        
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in {args.config_file}")
        print(f"   {e}")
        return 1
    except KeyError as e:
        print(f"❌ Error: Missing required key in config: {e}")
        print("   Config must have 'prompt_templates.templates' and 'prompt_templates.words'")
        return 1


if __name__ == "__main__":
    exit(main())