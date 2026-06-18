import sys
import os

# Ensure the 'app' module can be found regardless of where the script is run from
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.ml.data.dataset_loader import load_and_save_dataset
from app.ml.data.preprocess import preprocess_dataset

def main():
    print("=" * 50)
    print("🚀 Starting Crisis ML Dataset Pipeline")
    print("=" * 50)
    
    try:
        print("\n⏳ Downloading dataset...")
        load_and_save_dataset()
        
        print("\n⚙️ Preprocessing dataset...")
        preprocess_dataset()
        
        print("\n✅ Done! The dataset is ready for training.")
        
    except Exception as e:
        print(f"\n❌ Pipeline failed with an unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
