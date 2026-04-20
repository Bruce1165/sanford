import json
import os

# Category mapping based on screener types
category_mapping = {
    # Internal formulas
    "coffee_cup_handle_screener_v4": "内部公式",
    "daily_hot_cold_screener": "内部公式",
    "yin_feng_huang_screener": "内部公式",
    "jin_feng_huang_screener": "内部公式",
    "jin_feng_huang_screener": "内部公式",
    "zhang_ting_bei_liang_yin_screener": "内部公式",
    "shi_pan_xian_screener": "内部公式",
    "er_ban_hui_tiao_screener": "内部公式",
    
    # Classic formulas
    "ashare_21_screener": "经典公式",
    "ascending_triangle_screener": "经典公式",
    
    # Limit-up/flags (other)
    "coffee_cup_screener": "其它",
    "cup_handle_screener": "其它",
    "launch_31_screener": "其它",
    "shuang_shou_ban_screener": "其它",
    "high_tight_flag_screener": "其它",
}

config_dir = "/Users/mac/NeoTrade2/config/screeners"

for filename in os.listdir(config_dir):
    filepath = os.path.join(config_dir, filename)
    
    # Skip if not a JSON file
    if not filename.endswith('.json'):
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        config = json.load(f)
        
        # Get screener name (filename without .json)
        screener_name = filename[:-5]
        
        # Update category if in mapping
        if screener_name in category_mapping:
            new_category = category_mapping[screener_name]
            print(f"Updating {filename}: {config.get('category', '未分类')} -> {new_category}")
            config['category'] = new_category
            
            # Write back
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
    
print("Category update complete!")
