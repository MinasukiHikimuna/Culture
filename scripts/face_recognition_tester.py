import torch
from torchvision import transforms
from PIL import Image
import os
import argparse
from face_recognition_trainer import FaceRecognitionModel

class FaceRecognizer:
    def __init__(self, model_path):
        # Load the saved model and classes
        checkpoint = torch.load(model_path)
        self.classes = checkpoint['classes']
        
        # Print model info if available
        if 'training_params' in checkpoint:
            print("\nModel Information:")
            print("-" * 50)
            print(f"Training timestamp: {checkpoint.get('timestamp', 'Unknown')}")
            params = checkpoint['training_params']
            for key, value in params.items():
                print(f"{key}: {value}")
            print("-" * 50 + "\n")
        
        # Initialize model
        self.model = FaceRecognitionModel(num_classes=len(self.classes))
        self.model.load_state_dict(checkpoint['model_state_dict'])
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
        image = Image.open(image_path).convert('RGB')
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

def parse_args():
    parser = argparse.ArgumentParser(description='Test face recognition model')
    parser.add_argument('--model', type=str, required=True,
                      help='Path to the trained model file')
    parser.add_argument('--image', type=str,
                      help='Path to a single image to test')
    parser.add_argument('--dir', type=str,
                      help='Path to directory containing test images')
    parser.add_argument('--top-k', type=int, default=3,
                      help='Number of top predictions to show')
    return parser.parse_args()

def test_single_image(model_path, image_path, top_k=3):
    # Initialize recognizer
    recognizer = FaceRecognizer(model_path)
    
    # Test the image
    predictions = recognizer.predict(image_path, top_k=top_k)
    
    # Print results
    print(f"\nPredictions for {os.path.basename(image_path)}:")
    for performer, confidence in predictions:
        print(f"{performer}: {confidence*100:.2f}%")

def test_directory(model_path, dir_path, top_k=3):
    # Initialize recognizer
    recognizer = FaceRecognizer(model_path)
    
    # Test all images in directory
    for image_file in sorted(os.listdir(dir_path)):
        if image_file.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_path = os.path.join(dir_path, image_file)
            predictions = recognizer.predict(image_path, top_k=top_k)
            
            print(f"\nPredictions for {image_file}:")
            for performer, confidence in predictions:
                print(f"{performer}: {confidence*100:.2f}%")

if __name__ == "__main__":
    args = parse_args()
    
    if args.image:
        test_single_image(args.model, args.image, args.top_k)
    elif args.dir:
        test_directory(args.model, args.dir, args.top_k)
    else:
        print("Please provide either --image or --dir argument") 