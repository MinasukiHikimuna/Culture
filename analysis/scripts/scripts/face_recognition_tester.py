import argparse
import traceback
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from face_recognition_trainer import FaceRecognitionModel
from facenet_pytorch import MTCNN
from PIL import Image
from torchvision import transforms
from tqdm import tqdm


class FaceRecognizer:
    def __init__(self, model_path):
        # Load the saved model and classes
        checkpoint = torch.load(model_path)
        self.classes = checkpoint["classes"]

        # Print model info if available
        if "training_params" in checkpoint:
            print("\nModel Information:")
            print("-" * 50)
            print(f"Training timestamp: {checkpoint.get('timestamp', 'Unknown')}")
            params = checkpoint["training_params"]
            for key, value in params.items():
                print(f"{key}: {value}")
            print("-" * 50 + "\n")

        # Initialize model
        self.model = FaceRecognitionModel(num_classes=len(self.classes))
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()

        # Use GPU if available
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        self.model = self.model.to(self.device)

        # Define image transforms
        self.transform = transforms.Compose([
            transforms.Resize((160, 160)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
        ])

    def predict(self, image_path, top_k=3):
        """
        Predict the top k most likely performers for a face image

        Args:
            image_path: Path to the image file
            top_k: Number of top predictions to return

        Returns:
            List of tuples (performer_name, confidence_score)
        """
        # Load and transform image
        image = Image.open(image_path).convert("RGB")
        image_tensor = self.transform(image).unsqueeze(0).to(self.device)

        # Get model predictions
        with torch.no_grad():
            outputs = self.model(image_tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)

            # Get top k predictions
            top_probs, top_indices = probabilities[0].topk(min(top_k, len(self.classes)))

            # Convert to list of (performer, probability) tuples
            predictions = [
                (self.classes[idx], prob.item())
                for prob, idx in zip(top_probs, top_indices)
            ]

        return predictions

class FaceRecognitionTester:
    def __init__(self, model_path, device=None, verbose=False):
        """
        Initialize face recognition tester

        Args:
            model_path: Path to trained model checkpoint
            device: torch device (will use CUDA if available)
            verbose: Enable verbose output
        """
        self.verbose = verbose
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = device

        # Load model checkpoint
        checkpoint = torch.load(model_path, map_location=self.device)
        self.classes = checkpoint["classes"]

        # Initialize model
        self.model = FaceRecognitionModel(num_classes=len(self.classes))
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model = self.model.to(self.device)
        self.model.eval()

        # Initialize face detector
        self.face_detector = MTCNN(
            image_size=160,
            margin=20,
            min_face_size=60,
            thresholds=[0.7, 0.8, 0.8],
            post_process=True,
            select_largest=True,
            keep_all=False,
            device=self.device
        )

    def process_image(self, image_path):
        """Process single image and return face predictions"""
        try:
            if self.verbose:
                print(f"\nTesting image: {image_path}")

            img = Image.open(image_path).convert("RGB")
            faces = self.face_detector(img)

            if faces is None:
                if self.verbose:
                    print("No faces detected")
                return []

            # Ensure we only process one face per frame
            if isinstance(faces, list):
                faces = faces[0] if faces else None

            predictions = []

            # Process the face
            if faces is not None:
                face_tensor = faces

                if self.verbose:
                    print(f"Face tensor shape: {face_tensor.shape}")

                # Convert single channel to 3 channels if needed
                if len(face_tensor.shape) == 2:
                    face_tensor = face_tensor.unsqueeze(0).repeat(3, 1, 1)
                elif face_tensor.shape[0] == 1:
                    face_tensor = face_tensor.repeat(3, 1, 1)

                # Transform face for model
                face_tensor = face_tensor.unsqueeze(0).to(self.device)

                # Get model predictions
                with torch.no_grad():
                    outputs = self.model(face_tensor)
                    probabilities = F.softmax(outputs, dim=1)

                    # Get top 5 predictions
                    top_probs, top_indices = probabilities[0].topk(5)

                    face_predictions = [
                        (self.classes[idx], prob.item())
                        for idx, prob in zip(top_indices, top_probs)
                    ]
                    predictions.append(face_predictions)

            return predictions

        except Exception as e:
            if self.verbose:
                print(f"Error processing {image_path}: {e}")
                traceback.print_exc()
            return []

    def analyze_scene(self, image_paths, min_confidence=0.1):
        """Analyze multiple frames from a scene to identify likely performers"""
        all_predictions = defaultdict(list)
        total_frames = len(image_paths)

        print(f"\nProcessing {len(image_paths)} frames...")
        for img_path in tqdm(image_paths):
            frame_predictions = self.process_image(img_path)

            # Collect all predictions above threshold
            for face_preds in frame_predictions:
                for performer, confidence in face_preds:
                    if confidence >= min_confidence:
                        all_predictions[performer].append(confidence)

        # Debug: Print raw confidence values for top performers
        print("\nRaw confidence values for top performers:")
        for performer, confidences in list(all_predictions.items())[:3]:
            print(f"\n{performer}:")
            print(f"Number of detections: {len(confidences)}")
            print(f"Detection rate: {len(confidences)/total_frames:.2%}")
            print(f"Raw confidences: min={min(confidences):.4f}, max={max(confidences):.4f}, mean={np.mean(confidences):.4f}")
            print(f"Sample of confidence values: {confidences[:5]}")

        # Aggregate predictions
        aggregated_predictions = []

        for performer, confidences in all_predictions.items():
            # Calculate metrics
            max_conf = max(confidences)
            avg_conf = np.mean(confidences)
            detection_rate = len(confidences) / total_frames

            # Calculate final score - weighted average of:
            # - Average confidence of detections
            # - Best confidence seen
            # - How often detected in the scene
            confidence_score = (
                0.5 * avg_conf +        # Average detection confidence
                0.3 * max_conf +        # Best detection confidence
                0.2 * detection_rate    # Portion of frames where detected
            )

            if performer == list(all_predictions.keys())[0]:  # Debug first performer
                print(f"\nDetailed calculation for {performer}:")
                print(f"max_conf: {max_conf:.4f}")
                print(f"avg_conf: {avg_conf:.4f}")
                print(f"detection_rate: {detection_rate:.4f}")
                print("Final calculation:")
                print(f"0.5 * {avg_conf:.4f} = {0.5 * avg_conf:.4f}")
                print(f"0.3 * {max_conf:.4f} = {0.3 * max_conf:.4f}")
                print(f"0.2 * {detection_rate:.4f} = {0.2 * detection_rate:.4f}")
                print(f"Score = {confidence_score:.4f}")

            aggregated_predictions.append((
                performer,
                confidence_score,
                len(confidences)
            ))

        # Sort by confidence score
        aggregated_predictions.sort(key=lambda x: x[1], reverse=True)

        return aggregated_predictions

def parse_args():
    parser = argparse.ArgumentParser(description="Test face recognition model")
    parser.add_argument("--model", type=str, required=True,
                      help="Path to the trained model file")
    parser.add_argument("--image", type=str,
                      help="Path to a single image to test")
    parser.add_argument("--dir", type=str,
                      help="Path to directory containing test images")
    parser.add_argument("--top-k", type=int, default=3,
                      help="Number of top predictions to show")
    return parser.parse_args()

def test_single_image(model_path, image_path, top_k=3):
    # Initialize recognizer
    recognizer = FaceRecognizer(model_path)

    # Test the image
    predictions = recognizer.predict(image_path, top_k=top_k)

    # Print results
    print(f"\nPredictions for {Path(image_path).name}:")
    for performer, confidence in predictions:
        print(f"{performer}: {confidence*100:.2f}%")

def test_directory(model_path, dir_path, top_k=3):
    # Initialize recognizer
    recognizer = FaceRecognizer(model_path)

    # Test all images in directory
    for image_path_obj in sorted(Path(dir_path).iterdir()):
        if image_path_obj.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            image_path = str(image_path_obj)
            predictions = recognizer.predict(image_path, top_k=top_k)

            print(f"\nPredictions for {image_path_obj.name}:")
            for performer, confidence in predictions:
                print(f"{performer}: {confidence*100:.2f}%")

def main():
    parser = argparse.ArgumentParser(description="Test face recognition model on scene frames")
    parser.add_argument("--model", type=str, required=True,
                      help="Path to trained model checkpoint")
    parser.add_argument("--input", type=str, required=True,
                      help="Directory containing scene frames")
    parser.add_argument("--confidence", type=float, default=0.1,
                      help="Minimum confidence threshold")
    parser.add_argument("--verbose", action="store_true",
                      help="Enable verbose output")
    args = parser.parse_args()

    tester = FaceRecognitionTester(args.model, verbose=args.verbose)

    # Get all image files
    image_dir = Path(args.input)
    image_files = []
    for ext in [".jpg", ".png", ".webp"]:
        image_files.extend(list(image_dir.glob(f"*{ext}")))

    if not image_files:
        print(f"No images found in {image_dir}")
        return

    # Analyze scene
    results = tester.analyze_scene(image_files, args.confidence)

    # Print results
    print("\nScene Analysis Results:")
    print("-" * 60)
    print(f"{'Performer':<40} {'Score':<10} {'Detections'}")
    print("-" * 60)

    for performer, confidence, detections in results:
        print(f"{performer:<40} {confidence:>8.4f} {detections:>10}")

if __name__ == "__main__":
    main()
