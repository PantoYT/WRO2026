import json
import os

def process_json_file(file_path, ids_to_remove):
    """
    Process a JSON file by removing entries with specific IDs and reordering.
    """
    result = {
        'file': file_path,
        'removed_count': 0,
        'new_total': 0,
        'success': False,
        'error': None
    }
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            result['error'] = f'File not found: {file_path}'
            return result
        
        # Load JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Verify it is a list
        if not isinstance(data, list):
            result['error'] = f'JSON is not a list: {type(data)}'
            return result
        
        original_count = len(data)
        
        # Filter out entries with IDs to remove
        filtered_data = [entry for entry in data if str(entry.get('ID', entry.get('id', ''))).zfill(3) not in ids_to_remove]
        
        removed_count = original_count - len(filtered_data)
        
        # Reorder the order field sequentially starting from 1
        for idx, entry in enumerate(filtered_data, 1):
            entry['order'] = idx
        
        # Save back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, indent=2, ensure_ascii=False)
        
        result['removed_count'] = removed_count
        result['new_total'] = len(filtered_data)
        result['success'] = True
        
    except json.JSONDecodeError as e:
        result['error'] = f'JSON decode error: {str(e)}'
    except Exception as e:
        result['error'] = f'Unexpected error: {str(e)}'
    
    return result

# Process poems.json
poems_ids_to_remove = ['013', '014', '018', '019', '029', '041', '042', '043']
poems_result = process_json_file(r'assets\poems\poems.json', poems_ids_to_remove)

# Process music.json
music_ids_to_remove = ['015']
music_result = process_json_file(r'assets\music\music.json', music_ids_to_remove)

# Report results
print('=' * 60)
print('JSON FILE PROCESSING REPORT')
print('=' * 60)

print(f'\n1. POEMS.JSON')
print('-' * 60)
if poems_result['success']:
    print(f'   Status: SUCCESS')
    print(f'   Removed entries: {poems_result["removed_count"]}')
    print(f'   New total: {poems_result["new_total"]}')
    print(f'   IDs removed: {poems_ids_to_remove}')
else:
    print(f'   Status: FAILED')
    print(f'   Error: {poems_result["error"]}')

print(f'\n2. MUSIC.JSON')
print('-' * 60)
if music_result['success']:
    print(f'   Status: SUCCESS')
    print(f'   Removed entries: {music_result["removed_count"]}')
    print(f'   New total: {music_result["new_total"]}')
    print(f'   IDs removed: {music_ids_to_remove}')
else:
    print(f'   Status: FAILED')
    print(f'   Error: {music_result["error"]}')

print('\n' + '=' * 60)
