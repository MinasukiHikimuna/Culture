from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch
import torchvision.transforms.functional as TF
from facenet_pytorch import MTCNN
from PIL import Image
from tqdm import tqdm


class FacePreprocessor:
    def __init__(self, input_dir: Path, output_dir: Path, verbose: bool = False):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.verbose = verbose

        # Initialize MTCNN with stricter face detection
        self.mtcnn = MTCNN(
            image_size=160,
            margin=20,
            post_process=True,
            select_largest=True,
            min_face_size=60,
            thresholds=[0.7, 0.8, 0.8],
            device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
        )

    def align_face(self, image, landmarks):
        """Align face using eye landmarks"""
        left_eye = landmarks[0]
        right_eye = landmarks[1]

        # Calculate angle to align eyes horizontally
        dY = right_eye[1] - left_eye[1]
        dX = right_eye[0] - left_eye[0]
        angle = np.degrees(np.arctan2(dY, dX))

        # Rotate image
        rotated = TF.rotate(image, angle)

        return rotated

    def process_image(self, image_path: Path):
        """Process a single image"""
        try:
            if self.verbose:
                print(f"\nProcessing image: {image_path}")

            # Load image and ensure RGB
            image = Image.open(image_path).convert("RGB")
            if self.verbose:
                print(f"Loaded image mode: {image.mode}")

            # Get both face tensor and detection probability
            face_tensor, prob = self.mtcnn(image, return_prob=True)

            if face_tensor is None:
                if self.verbose:
                    print(f"No face detected in {image_path}")
                return False

            if prob < 0.92:
                if self.verbose:
                    print(f"Low confidence detection ({prob:.2f}) in {image_path}")
                return False

            if not self._check_face_quality(face_tensor):
                return False

            # Denormalize and convert to PIL Image
            face_tensor = (face_tensor + 1) / 2 * 255
            face_tensor = face_tensor.byte()
            face_image = TF.to_pil_image(face_tensor)

            # Save processed face image
            rel_path = image_path.relative_to(self.input_dir)
            output_path = self.output_dir / rel_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            face_image.save(output_path, quality=95)

            if self.verbose:
                print(f"Saved face to: {output_path}")

            return True

        except Exception as e:
            if self.verbose:
                print(f"Error processing {image_path}: {e}")
                import traceback
                traceback.print_exc()
            return False

    def _check_face_quality(self, face_tensor):
        """Additional quality checks for detected faces"""
        try:
            # Convert tensor to numpy for checks
            face = face_tensor.permute(1, 2, 0).cpu().numpy()

            # Check for reasonable face proportions (not too stretched)
            height, width = face.shape[:2]
            aspect_ratio = width / height
            if not (0.8 <= aspect_ratio <= 1.2):
                print(f"Failed aspect ratio check: {aspect_ratio:.2f}")
                return False

            # Check for extreme brightness/darkness
            normalized_brightness = (face.mean() + 1) / 2
            if normalized_brightness < 0.15 or normalized_brightness > 0.85:
                print(f"Failed brightness check: {normalized_brightness:.2f}")
                return False

            # Check for sufficient variance (avoid solid color regions)
            std_dev = face.std()
            if std_dev < 0.15:
                print(f"Failed variance check: {std_dev:.2f}")
                return False

            # Enhanced face centering check
            h, w = face.shape[:2]
            # Check multiple regions to ensure face features are present
            center_region = face[h//4:3*h//4, w//4:3*w//4]
            upper_region = face[h//8:3*h//8, w//4:3*w//4]  # Where eyes should be
            lower_region = face[5*h//8:7*h//8, w//4:3*w//4]  # Where mouth should be

            # Check for feature variance in each region
            if (center_region.std() < 0.12 or  # Center should have good detail
                upper_region.std() < 0.1 or    # Eyes region should have variance
                lower_region.std() < 0.1):     # Mouth region should have variance
                print("Failed facial features check")
                return False

            # Check for contrast in the face region
            face_gray = face.mean(axis=2)  # Convert to grayscale
            percentile_95 = np.percentile(face_gray, 95)
            percentile_5 = np.percentile(face_gray, 5)
            contrast = percentile_95 - percentile_5

            if contrast < 0.3:  # Require some minimum contrast
                print(f"Failed contrast check: {contrast:.2f}")
                return False

            return True

        except Exception as e:
            print(f"Error in face quality check: {e}")
            return False

    def process_dataset(self, num_workers=4):
        """Process entire dataset with progress tracking"""
        print("\nStarting face preprocessing:")
        print(f"Input directory: {self.input_dir}")
        print(f"Output directory: {self.output_dir}")
        print(f"Using {num_workers} worker processes")
        print(f"Using device: {self.mtcnn.device}\n")

        # Get all image files
        print("Scanning for images...")
        image_files = list(self.input_dir.rglob("*.jpg")) + \
                     list(self.input_dir.rglob("*.png")) + \
                     list(self.input_dir.rglob("*.webp"))
        total_images = len(image_files)

        if total_images == 0:
            print(f"No images found in {self.input_dir}")
            return

        print(f"Found {total_images} images to process")
        print("Sample paths:")
        for path in image_files[:5]:
            print(f"  {path}")
        if total_images > 5:
            print(f"  ... and {total_images-5} more files")

        print("\nStarting image processing...")

        # Process images in parallel
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            results = list(tqdm(
                executor.map(self.process_image, image_files),
                total=total_images,
                desc="Processing images"
            ))

        # Print statistics
        processed = sum(results)
        failed = total_images - processed

        print("\nProcessing complete:")
        print(f"Total images: {total_images}")
        print(f"Successfully processed: {processed} images ({processed/total_images*100:.1f}%)")
        print(f"Failed: {failed} images ({failed/total_images*100:.1f}%)")

        if processed > 0:
            print("\nSample output paths:")
            output_files = list(self.output_dir.rglob("*.jpg"))[:5]
            for path in output_files:
                print(f"  {path}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Preprocess face dataset")
    parser.add_argument("--input", type=str, required=True,
                      help="Input directory containing face images")
    parser.add_argument("--output", type=str, required=True,
                      help="Output directory for preprocessed images")
    parser.add_argument("--workers", type=int, default=4,
                      help="Number of worker processes")
    args = parser.parse_args()

    try:
        input_dir = Path(args.input)
        output_dir = Path(args.output)

        if not input_dir.exists():
            print(f"Error: Input directory does not exist: {input_dir}")
            return

        print("\nPreprocessing face dataset:")
        print(f"Input directory: {input_dir}")
        print(f"Output directory: {output_dir}")

        preprocessor = FacePreprocessor(input_dir, output_dir)
        preprocessor.process_dataset(num_workers=args.workers)

    except KeyboardInterrupt:
        print("\nProcessing interrupted by user")
    except Exception as e:
        print(f"\nError: {str(e)}")
        raise

if __name__ == "__main__":
    main()
