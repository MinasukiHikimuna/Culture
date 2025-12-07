from ultralytics import YOLO
from pathlib import Path
import argparse

def process_directory(source_dir: str, model_name: str = "yolo11n.pt", save_results: bool = True):
    """
    Process all images in the given directory using YOLO11
    
    Args:
        source_dir (str): Path to directory containing images
        model_name (str): Name of the YOLO model to use
        save_results (bool): Whether to save annotated images
    """
    # Load the YOLO model
    model = YOLO(model_name)  # Using YOLO11 model
    
    # Get all image files
    source_path = Path(source_dir)
    image_files = []
    for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
        image_files.extend(source_path.glob(f'*{ext}'))
        image_files.extend(source_path.glob(f'*{ext.upper()}'))

    if not image_files:
        print(f"No images found in {source_dir}")
        return

    # Create yolo directory at the same level as source directory
    output_dir = source_path.parent / 'yolo'
    output_dir.mkdir(exist_ok=True)

    # Process each image
    for img_path in image_files:
        print(f"\nProcessing {img_path}")
        
        # Run inference and save results directly
        if save_results:
            # Save directly to the yolo directory
            results = model(img_path, verbose=False, save=True, 
                          project=str(output_dir),
                          name='',
                          exist_ok=True,
                          save_txt=False,
                          save_conf=False,
                          save_crop=False)
        else:
            results = model(img_path, verbose=False)
        
        # Process and display results
        for result in results:
            boxes = result.boxes
            print(f"Found {len(boxes)} objects")
            
            for box in boxes:
                class_name = result.names[int(box.cls[0])]
                confidence = float(box.conf[0])
                print(f"- {class_name}: {confidence:.2f}")

            # Move the file from predict subdirectory if it exists
            if save_results:
                predict_dir = output_dir / 'predict'
                if predict_dir.exists():
                    for pred_file in predict_dir.glob('*'):
                        target_file = output_dir / pred_file.name
                        pred_file.rename(target_file)
                    predict_dir.rmdir()

def main():
    parser = argparse.ArgumentParser(description='Detect objects in images using YOLO11')
    parser.add_argument('source_dir', type=str, help='Directory containing images')
    parser.add_argument('--model', type=str, default='yolo11n.pt',
                        help='YOLO11 model to use (default: yolo11n.pt)')
    parser.add_argument('--no-save', action='store_true',
                        help='Do not save annotated images')
    
    args = parser.parse_args()
    
    source_path = Path(args.source_dir)
    if not source_path.exists():
        print(f"Error: Directory {args.source_dir} does not exist")
        return
    
    process_directory(str(source_path), args.model, not args.no_save)

if __name__ == "__main__":
    main() 