import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from facenet_pytorch import InceptionResnetV1
from PIL import Image
import os
from pathlib import Path
import numpy as np
import random
from datetime import datetime
import sys

class FaceDataset(Dataset):
    def __init__(self, root_dir, transform=None, min_scenes=2):
        """
        Args:
            root_dir (string): Directory with all the face images organized in performer folders
            transform (callable, optional): Optional transform to be applied on a sample
            min_scenes (int): Minimum number of different scenes required for a performer
        """
        self.root_dir = Path(root_dir)
        self.transform = transform
        self.classes = []
        self.class_to_idx = {}
        self.samples = []
        
        # First pass: collect scene information per performer
        performer_scenes = {}  # {performer_id: set(scene_ids)}
        valid_performers = []
        
        for performer_dir in sorted(self.root_dir.iterdir()):
            if performer_dir.is_dir():
                performer_id = performer_dir.name.split(" - ")[0]
                scene_ids = set()
                
                for img_path in performer_dir.glob("*.jpg"):
                    scene_id = img_path.name.split("_")[0]
                    scene_ids.add(scene_id)
                
                if len(scene_ids) >= min_scenes:
                    performer_scenes[performer_id] = scene_ids
                    valid_performers.append(performer_dir)
        
        # Second pass: create dataset only with valid performers
        for idx, performer_dir in enumerate(valid_performers):  # Use valid_performers list
            performer_id, performer_name = performer_dir.name.split(" - ", 1)
            self.classes.append(performer_name)
            self.class_to_idx[performer_name] = idx
            
            # Collect all images for this performer
            for img_path in performer_dir.glob("*.jpg"):
                self.samples.append((str(img_path), idx))
        
        print(f"Loaded {len(self.classes)} performers with at least {min_scenes} scenes each")
        print(f"Total samples: {len(self.samples)}")
        
        # Verify class indices
        max_class_idx = max(idx for _, idx in self.samples)
        assert max_class_idx < len(self.classes), f"Max class index {max_class_idx} >= number of classes {len(self.classes)}"
    
    def split_by_scenes(self, val_ratio=0.2):
        """
        Split dataset into training and validation sets based on scenes
        
        Args:
            val_ratio (float): Ratio of scenes to use for validation
            
        Returns:
            train_indices, val_indices
        """
        # Group samples by performer and scene
        performer_scenes = {}  # {performer_idx: {scene_id: [sample_indices]}}
        
        for idx, (img_path, performer_idx) in enumerate(self.samples):
            scene_id = Path(img_path).name.split("_")[0]
            
            if performer_idx not in performer_scenes:
                performer_scenes[performer_idx] = {}
            if scene_id not in performer_scenes[performer_idx]:
                performer_scenes[performer_idx][scene_id] = []
            
            performer_scenes[performer_idx][scene_id].append(idx)
        
        train_indices = []
        val_indices = []
        
        # For each performer, split their scenes into train/val
        for performer_idx, scenes in performer_scenes.items():
            scene_ids = list(scenes.keys())
            num_val_scenes = max(1, int(len(scene_ids) * val_ratio))
            
            # Randomly select validation scenes
            val_scenes = set(random.sample(scene_ids, num_val_scenes))
            
            # Assign indices to train/val based on scenes
            for scene_id, indices in scenes.items():
                if scene_id in val_scenes:
                    val_indices.extend(indices)
                else:
                    train_indices.extend(indices)
        
        print(f"Split dataset into {len(train_indices)} training and {len(val_indices)} validation samples")
        return train_indices, val_indices

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, label = self.samples[idx]
        image = Image.open(img_path).convert('RGB')
        
        if self.transform:
            image = self.transform(image)
            
        return image, label

class FaceRecognitionModel(nn.Module):
    def __init__(self, num_classes):
        super(FaceRecognitionModel, self).__init__()
        # Load pretrained FaceNet model
        self.backbone = InceptionResnetV1(pretrained='vggface2')
        
        # Freeze the backbone
        for param in self.backbone.parameters():
            param.requires_grad = False
            
        # Add more sophisticated classifier layers
        self.classifier = nn.Sequential(
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, num_classes)
        )
        
    def forward(self, x):
        features = self.backbone(x)
        return self.classifier(features)

def train_model(dataset_path, batch_size=32, num_epochs=10, learning_rate=0.0001, log_file=None):
    # Redirect stdout to both console and file
    if log_file:
        class Logger:
            def __init__(self, filename):
                self.terminal = sys.stdout
                self.log = open(filename, 'w')
            
            def write(self, message):
                self.terminal.write(message)
                self.log.write(message)
                self.log.flush()
            
            def flush(self):
                self.terminal.flush()
                self.log.flush()
        
        sys.stdout = Logger(log_file)
    
    # Log training parameters
    print(f"Training started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Dataset path: {dataset_path}")
    print(f"Batch size: {batch_size}")
    print(f"Learning rate: {learning_rate}")
    print(f"Max epochs: {num_epochs}\n")
    
    # Set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Define transforms with augmentation
    train_transform = transforms.Compose([
        transforms.Resize((160, 160)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
    ])
    
    val_transform = transforms.Compose([
        transforms.Resize((160, 160)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
    ])
    
    # Create datasets with appropriate transforms
    full_dataset = FaceDataset(dataset_path, transform=None, min_scenes=2)  # No transform yet
    train_indices, val_indices = full_dataset.split_by_scenes(val_ratio=0.2)
    
    # Create train/val datasets with different transforms
    train_dataset = TransformSubset(full_dataset, train_indices, train_transform)
    val_dataset = TransformSubset(full_dataset, val_indices, val_transform)
    
    # Create data loaders
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)
    
    # Initialize model
    model = FaceRecognitionModel(num_classes=len(full_dataset.classes))
    model = model.to(device)
    
    # Define loss function and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.classifier.parameters(), lr=learning_rate)
    
    # Add learning rate scheduler without verbose flag
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='max', factor=0.1, patience=2
    )
    
    # Add early stopping
    best_val_acc = 0
    best_model_state = None
    patience = 5
    patience_counter = 0
    
    # Training loop
    for epoch in range(num_epochs):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        
        # Progress tracking
        print(f'\nEpoch {epoch+1}/{num_epochs}')
        print('-' * 60)
        
        for batch_idx, (inputs, labels) in enumerate(train_loader):
            inputs, labels = inputs.to(device), labels.to(device)
            
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
            
            # Print batch progress
            if (batch_idx + 1) % 10 == 0:
                print(f'Batch [{batch_idx+1}/{len(train_loader)}] | '
                      f'Loss: {running_loss/(batch_idx+1):.3f} | '
                      f'Acc: {100.*correct/total:.2f}%')
        
        train_accuracy = 100. * correct / total
        
        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        print('\nValidating...')
        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                
                val_loss += loss.item()
                _, predicted = outputs.max(1)
                val_total += labels.size(0)
                val_correct += predicted.eq(labels).sum().item()
        
        val_accuracy = 100. * val_correct / val_total
        
        # Print epoch summary
        print('\nEpoch Summary:')
        print(f'Training Loss: {running_loss/len(train_loader):.3f}')
        print(f'Training Accuracy: {train_accuracy:.2f}%')
        print(f'Validation Loss: {val_loss/len(val_loader):.3f}')
        print(f'Validation Accuracy: {val_accuracy:.2f}%')
        print(f'Learning Rate: {optimizer.param_groups[0]["lr"]:.6f}')
        
        # Update learning rate
        scheduler.step(val_accuracy)
        
        # Save best model
        if val_accuracy > best_val_acc:
            print(f'Validation accuracy improved from {best_val_acc:.2f}% to {val_accuracy:.2f}%')
            best_val_acc = val_accuracy
            best_model_state = model.state_dict()
            patience_counter = 0
        else:
            patience_counter += 1
            print(f'Validation accuracy did not improve. {patience-patience_counter} epochs until early stopping.')
        
        if patience_counter >= patience:
            print("\nEarly stopping triggered!")
            break
    
    # Restore best model
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
        print(f'\nRestored best model with validation accuracy: {best_val_acc:.2f}%')
    
    # Print final results
    print("\nTraining completed!")
    print(f"Best validation accuracy: {best_val_acc:.2f}%")
    print(f"Training finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Restore stdout if needed
    if log_file:
        sys.stdout = sys.stdout.terminal
    
    return model, full_dataset.classes

class TransformSubset(Dataset):
    """Dataset wrapper that applies different transforms to a subset of data"""
    def __init__(self, dataset, indices, transform):
        self.dataset = dataset
        self.indices = indices
        self.transform = transform
    
    def __getitem__(self, idx):
        image, label = self.dataset.samples[self.indices[idx]]
        image = Image.open(image).convert('RGB')
        if self.transform:
            image = self.transform(image)
        return image, label
    
    def __len__(self):
        return len(self.indices)

if __name__ == "__main__":
    # Generate timestamp for this training run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create output directory
    output_dir = Path(os.path.dirname(__file__)) / "training_runs"
    output_dir.mkdir(exist_ok=True)
    
    # Setup paths for model and log file
    model_path = output_dir / f"face_recognition_model_{timestamp}.pth"
    log_path = output_dir / f"training_log_{timestamp}.txt"
    
    # Convert Windows path to WSL path
    dataset_path = "/mnt/h/Faces/dataset/performers/deduplicated"
    
    # Train model with logging
    model, classes = train_model(dataset_path, log_file=str(log_path))
    
    # Save the model
    torch.save({
        'model_state_dict': model.state_dict(),
        'classes': classes,
        'timestamp': timestamp,
        'training_params': {
            'batch_size': 32,
            'learning_rate': 0.0001,
            'architecture': 'FaceNet + Custom Classifier',
            'dataset_path': dataset_path
        }
    }, model_path)
    
    print(f"\nTraining run {timestamp} completed:")
    print(f"Model saved to: {model_path}")
    print(f"Training log saved to: {log_path}") 