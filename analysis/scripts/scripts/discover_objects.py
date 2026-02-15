import argparse
from pathlib import Path

import cv2
import numpy as np
from sklearn.cluster import DBSCAN
from ultralytics import YOLO


def extract_object(image, box_coords, padding=10):
    """Extract object from image with padding"""
    x1, y1, x2, y2 = [int(coord) for coord in box_coords]

    # Add padding while keeping within image bounds
    height, width = image.shape[:2]
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(width, x2 + padding)
    y2 = min(height, y2 + padding)

    return image[y1:y2, x1:x2]

def discover_objects(source_dir: str, confidence_threshold: float = 0.25, save_results: bool = True):
    """
    Discover potential new objects using unsupervised learning and save cropped objects
    """
    model = YOLO("yolo11n.pt")

    source_path = Path(source_dir)
    output_dir = source_path.parent / "discoveries"
    output_dir.mkdir(exist_ok=True)

    # Create directory for extracted objects
    objects_dir = output_dir / "extracted_objects"
    objects_dir.mkdir(exist_ok=True)

    image_files = []
    for ext in [".jpg", ".jpeg", ".png", ".bmp"]:
        image_files.extend(source_path.glob(f"*{ext}"))

    unknown_features = []
    locations = []

    for img_path in image_files:
        print(f"\nAnalyzing {img_path}")

        # Load image for cropping
        image = cv2.imread(str(img_path))
        if image is None:
            print(f"Failed to load {img_path}")
            continue

        results = model.predict(
            source=img_path,
            verbose=False,
            conf=0.01,
            save=save_results,
            project=str(output_dir),
            name=""
        )

        for result in results:
            for box in result.boxes:
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])

                if class_id != 0 or confidence < 0.3:
                    box_coords = box.xyxy[0].tolist()

                    # Extract features
                    width = box_coords[2] - box_coords[0]
                    height = box_coords[3] - box_coords[1]
                    aspect_ratio = width / height if height > 0 else 0
                    area = width * height
                    center_x = (box_coords[0] + box_coords[2]) / 2
                    center_y = (box_coords[1] + box_coords[3]) / 2

                    features = [
                        width / 100,
                        height / 100,
                        aspect_ratio,
                        area / 10000,
                        center_x / 1000,
                        center_y / 1000
                    ]

                    unknown_features.append(features)
                    locations.append({
                        "image": img_path,
                        "box": box_coords,
                        "confidence": confidence,
                        "class_id": class_id,
                        "class_name": model.names[class_id],
                        "extracted_object": extract_object(image, box_coords)
                    })

    if unknown_features:
        features_array = np.array(unknown_features)
        features_mean = np.mean(features_array, axis=0)
        features_std = np.std(features_array, axis=0)
        features_normalized = (features_array - features_mean) / (features_std + 1e-10)

        clustering = DBSCAN(eps=1.0, min_samples=2)
        clusters = clustering.fit_predict(features_normalized)

        unique_clusters = np.unique(clusters)
        print(f"\nDiscovered {len(unique_clusters)} potential new object classes")

        for cluster_id in unique_clusters:
            if cluster_id == -1:
                continue

            # Create directory for this cluster
            cluster_dir = objects_dir / f"cluster_{cluster_id}"
            cluster_dir.mkdir(exist_ok=True)

            cluster_locations = [loc for i, loc in enumerate(locations)
                               if clusters[i] == cluster_id]

            cluster_features = features_array[clusters == cluster_id]
            avg_width = np.mean(cluster_features[:, 0]) * 100
            avg_height = np.mean(cluster_features[:, 1]) * 100
            avg_aspect = np.mean(cluster_features[:, 2])

            print(f"\nPotential new object class {cluster_id}:")
            print(f"Found in {len(cluster_locations)} locations")
            print(f"Average dimensions: {avg_width:.1f}x{avg_height:.1f} pixels")
            print(f"Average aspect ratio: {avg_aspect:.2f}")

            # Save extracted objects for this cluster
            for i, loc in enumerate(cluster_locations):
                output_path = cluster_dir / f"object_{i:04d}.jpg"
                cv2.imwrite(str(output_path), loc["extracted_object"])
                print(f"- Saved {output_path.name} from {loc['image'].name} "
                      f"(confidence: {loc['confidence']:.2f}, "
                      f"current guess: {loc['class_name']})")

def main():
    parser = argparse.ArgumentParser(description="Discover and extract new objects from images")
    parser.add_argument("source_dir", type=str, help="Directory containing images")
    parser.add_argument("--confidence", type=float, default=0.25,
                        help="Confidence threshold for potential objects")
    parser.add_argument("--no-save", action="store_true",
                        help="Do not save annotated images")

    args = parser.parse_args()

    discover_objects(args.source_dir, args.confidence, not args.no_save)

if __name__ == "__main__":
    main()