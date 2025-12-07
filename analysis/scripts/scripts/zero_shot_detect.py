from ultralytics import YOLO
from pathlib import Path
import argparse

def detect_with_descriptions(source_dir: str, descriptions: list, save_results: bool = True):
    """
    Detect objects using natural language descriptions, excluding people
    
    Args:
        source_dir (str): Path to directory containing images
        descriptions (list): List of object descriptions in natural language
        save_results (bool): Whether to save annotated images
    """
    # Load YOLO model
    model = YOLO('yolo11n.pt')
    
    # Get all image files
    source_path = Path(source_dir)
    image_files = []
    for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
        image_files.extend(source_path.glob(f'*{ext}'))
        image_files.extend(source_path.glob(f'*{ext.upper()}'))

    # Create output directory
    output_dir = source_path.parent / 'yolo'
    output_dir.mkdir(exist_ok=True)

    # Process each image
    for img_path in image_files:
        print(f"\nProcessing {img_path}")
        
        # First detect people
        person_results = model.predict(
            source=img_path,
            verbose=False,
            conf=0.3,
            classes=[0],  # Class 0 is person in COCO dataset
            task='detect'
        )
        
        # Get person bounding boxes
        person_boxes = []
        for result in person_results:
            for box in result.boxes:
                if box.conf > 0.3:  # Confidence threshold for people
                    person_boxes.append(box.xyxy[0].tolist())
        
        # Now run detection for other objects
        results = model.predict(
            source=img_path,
            verbose=False,
            save=save_results,
            project=str(output_dir),
            name='',
            exist_ok=True,
            conf=0.25,
            task='detect'
        )
        
        # Process results
        for result in results:
            boxes = result.boxes
            filtered_boxes = []
            
            # Filter out detections that significantly overlap with person boxes
            for box in boxes:
                box_coords = box.xyxy[0].tolist()
                is_person = False
                
                for person_box in person_boxes:
                    # Calculate IoU (Intersection over Union)
                    intersection = [
                        max(box_coords[0], person_box[0]),
                        max(box_coords[1], person_box[1]),
                        min(box_coords[2], person_box[2]),
                        min(box_coords[3], person_box[3])
                    ]
                    
                    if (intersection[2] > intersection[0] and intersection[3] > intersection[1]):
                        # Calculate areas
                        intersection_area = (intersection[2] - intersection[0]) * (intersection[3] - intersection[1])
                        box_area = (box_coords[2] - box_coords[0]) * (box_coords[3] - box_coords[1])
                        person_area = (person_box[2] - person_box[0]) * (person_box[3] - person_box[1])
                        union_area = box_area + person_area - intersection_area
                        
                        iou = intersection_area / union_area
                        if iou > 0.7:  # High overlap threshold
                            is_person = True
                            break
                
                if not is_person:
                    filtered_boxes.append((box_coords, float(box.conf[0])))
            
            print(f"Found {len(filtered_boxes)} non-person objects")
            
            # Print filtered detections
            for box_coords, confidence in filtered_boxes:
                print(f"- Object detected at {box_coords} with confidence: {confidence:.2f}")
                print(f"  This might match descriptions: {', '.join(descriptions)}")

def main():
    parser = argparse.ArgumentParser(description='Object detection with custom descriptions, excluding people')
    parser.add_argument('source_dir', type=str, help='Directory containing images')
    parser.add_argument('--descriptions', nargs='+', required=True,
                        help='Natural language descriptions of objects to detect')
    parser.add_argument('--no-save', action='store_true',
                        help='Do not save annotated images')
    
    args = parser.parse_args()
    
    detect_with_descriptions(args.source_dir, args.descriptions, not args.no_save)

if __name__ == "__main__":
    main() 