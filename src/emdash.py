import os
import fnmatch

def clean_file(filepath):
    """Replaces em-dashes with standard dashes in a file."""
    try:
        # Read the file using utf-8-sig to handle potential BOMs
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        
        # Check if the em-dash exists
        em_dash = '\u2014' # The '-' character
        if em_dash in content:
            new_content = content.replace(em_dash, '-')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    root_dir = "." # Assumes running from src/
    count = 0
    print(f"Scanning {os.path.abspath(root_dir)} for em-dashes in .py files...")
    
    for root, dirs, files in os.walk(root_dir):
        for filename in fnmatch.filter(files, "*.py"):
            filepath = os.path.join(root, filename)
            if clean_file(filepath):
                print(f"Fixed: {filepath}")
                count += 1

    print(f"\nScan complete. Fixed {count} files.")

if __name__ == "__main__":
    main()