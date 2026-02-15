import argparse
import os
import random
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from facenet_pytorch import MTCNN, InceptionResnetV1
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms


class FaceDataset(Dataset):
    def __init__(self, root_dir, transform=None, min_images=2, source_type="scene"):
        """
        Args:
            root_dir (string): Directory with preprocessed face images
            transform (callable, optional): Optional transform to be applied
            min_images (int): Minimum number of images required per performer
            source_type (str): Either "scene" or "stashdb" to handle different naming patterns
        """
        self.root_dir = Path(root_dir)
        self.transform = transform
        self.classes = []
        self.class_to_idx = {}
        self.samples = []

        # Load preprocessed images
        for performer_dir in sorted(self.root_dir.iterdir()):
            if performer_dir.is_dir():
                # Get performer ID and name based on source type
                if source_type == "stashdb":
                    # StashDB format: "uuid - Name"
                    performer_id, performer_name = performer_dir.name.split(" - ", 1)
                else:
                    # Scene format: Use directory name as both ID and name
                    performer_id = performer_name = performer_dir.name

                # Count images for this performer
                image_files = list(performer_dir.glob("*.jpg")) + \
                            list(performer_dir.glob("*.png")) + \
                            list(performer_dir.glob("*.webp"))

                if len(image_files) >= min_images:
                    idx = len(self.classes)
                    self.classes.append(performer_name)
                    self.class_to_idx[performer_name] = idx

                    for img_path in image_files:
                        self.samples.append((str(img_path), idx))

    def split_dataset(self, val_ratio=0.2):
        """Split dataset randomly since we don't need scene-based splitting for StashDB"""
        # Group images by performer
        performer_images = {}
        for img_path, label in self.samples:
            performer = self.classes[label]
            if performer not in performer_images:
                performer_images[performer] = []
            performer_images[performer].append((img_path, label))

        train_indices = []
        val_indices = []

        # Split images for each performer
        for performer, images in performer_images.items():
            # Shuffle images
            random.shuffle(images)

            # Calculate split point
            val_size = max(1, int(len(images) * val_ratio))
            train_size = len(images) - val_size

            # Add images to appropriate split
            for img_idx, (img_path, label) in enumerate(images):
                if img_idx < train_size:
                    train_indices.append(self.samples.index((img_path, label)))
                else:
                    val_indices.append(self.samples.index((img_path, label)))

        print(f"Split dataset into {len(train_indices)} training and {len(val_indices)} validation samples")
        return train_indices, val_indices

    def __getitem__(self, idx):
        img_path, label = self.samples[idx]
        image = Image.open(img_path).convert("RGB")

        if self.transform:
            image = self.transform(image)

        return image, label

class FaceRecognitionModel(nn.Module):
    def __init__(self, num_classes):
        super(FaceRecognitionModel, self).__init__()
        # Load pretrained FaceNet model
        self.backbone = InceptionResnetV1(pretrained="vggface2")

        # Freeze more layers to reduce overfitting (freeze 80%)
        trainable_layers = int(len(list(self.backbone.parameters())) * 0.2)  # Changed from 0.4
        for param in list(self.backbone.parameters())[:-trainable_layers]:
            param.requires_grad = False

        # Simplified classifier with stronger regularization
        self.classifier = nn.Sequential(
            nn.Linear(512, 256),
            nn.BatchNorm1d(256, momentum=0.1),
            nn.ReLU(),
            nn.Dropout(0.5),  # Increased dropout

            nn.Linear(256, num_classes)
        )

    def forward(self, x):
        features = self.backbone(x)
        return self.classifier(features)

def copy_dataset_split(dataset, indices, output_dir: Path, split_name: str):
    """Copy dataset split to a new directory for inspection"""
    split_dir = output_dir / split_name
    split_dir.mkdir(parents=True, exist_ok=True)

    # Create performer directories and copy images
    for idx in indices:
        img_path, label = dataset.samples[idx]
        performer_name = dataset.classes[label]

        # Create performer directory
        performer_dir = split_dir / performer_name
        performer_dir.mkdir(exist_ok=True)

        # Copy image
        img_path = Path(img_path)
        dest_path = performer_dir / img_path.name
        if not dest_path.exists():  # Skip if already copied
            dest_path.write_bytes(img_path.read_bytes())

    print(f"Copied {len(indices)} images to {split_dir}")
    return split_dir

def train_model(dataset_path, batch_size=32, num_epochs=50, learning_rate=0.0001, log_file=None, source_type="scene"):
    # Redirect stdout to both console and file
    if log_file:
        class Logger:
            def __init__(self, filename):
                self.terminal = sys.stdout
                self.log = open(filename, "w")

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

    # Enhanced data augmentation to improve generalization
    train_transform = transforms.Compose([
        transforms.Resize((160, 160)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(20),  # Increased rotation
        transforms.ColorJitter(
            brightness=0.3,  # Increased color augmentation
            contrast=0.3,
            saturation=0.3,
            hue=0.15
        ),
        transforms.RandomAffine(
            degrees=0,
            translate=(0.15, 0.15),  # Increased translation
            scale=(0.85, 1.15)  # Increased scale variation
        ),
        transforms.RandomPerspective(distortion_scale=0.2, p=0.5),  # Added perspective transform
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
    ])

    val_transform = transforms.Compose([
        transforms.Resize((160, 160)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
    ])

    # Create datasets with appropriate transforms
    full_dataset = FaceDataset(dataset_path, transform=None, min_images=2, source_type=source_type)
    train_indices, val_indices = full_dataset.split_dataset(val_ratio=0.2)

    # Copy splits for inspection
    output_dir = Path(os.path.dirname(log_file)).parent if log_file else Path("training_runs")
    train_dir = copy_dataset_split(full_dataset, train_indices, output_dir, f"train_split_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    val_dir = copy_dataset_split(full_dataset, val_indices, output_dir, f"val_split_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    print(f"\nDataset splits copied to:")
    print(f"Training: {train_dir}")
    print(f"Validation: {val_dir}\n")

    # Create train/val datasets with transforms
    train_dataset = TransformSubset(full_dataset, train_indices, train_transform)
    val_dataset = TransformSubset(full_dataset, val_indices, val_transform)

    # Ensure we have enough samples for batch size
    if len(train_dataset) < batch_size or len(val_dataset) < batch_size:
        raise ValueError(f"Not enough samples for batch_size={batch_size}. "
                       f"Got {len(train_dataset)} training and {len(val_dataset)} validation samples.")

    # Create data loaders with drop_last=True
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, drop_last=True)

    # Initialize model
    model = FaceRecognitionModel(num_classes=len(full_dataset.classes))
    model = model.to(device)

    # Use weighted loss for class imbalance
    class_counts = torch.zeros(len(full_dataset.classes))
    for _, label in full_dataset.samples:
        class_counts[label] += 1
    class_weights = 1.0 / class_counts
    class_weights = class_weights / class_weights.sum()
    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))

    # Use different optimizers for backbone and classifier
    backbone_params = list(model.backbone.parameters())[-20:]  # Last few layers
    classifier_params = model.classifier.parameters()

    optimizer = torch.optim.AdamW([
        {"params": backbone_params, "lr": learning_rate * 0.1},
        {"params": classifier_params, "lr": learning_rate}
    ], weight_decay=0.01)  # Increased weight decay

    # Improved scheduler with longer cycles
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=10, T_mult=2, eta_min=1e-7
    )

    # Increased patience for early stopping
    patience = 10
    best_val_acc = 0
    best_model_state = None
    patience_counter = 0

    # Training loop
    for epoch in range(num_epochs):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        # Progress tracking
        print(f"\nEpoch {epoch+1}/{num_epochs}")
        print("-" * 60)

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
                print(f"Batch [{batch_idx+1}/{len(train_loader)}] | "
                      f"Loss: {running_loss/(batch_idx+1):.3f} | "
                      f"Acc: {100.*correct/total:.2f}%")

        train_accuracy = 100. * correct / total

        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        print("\nValidating...")
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
        print("\nEpoch Summary:")
        print(f"Training Loss: {running_loss/len(train_loader):.3f}")
        print(f"Training Accuracy: {train_accuracy:.2f}%")
        print(f"Validation Loss: {val_loss/len(val_loader):.3f}")
        print(f"Validation Accuracy: {val_accuracy:.2f}%")
        print(f'Learning Rate: {optimizer.param_groups[0]["lr"]:.6f}')

        # Update learning rate
        scheduler.step()

        # Save best model
        if val_accuracy > best_val_acc:
            print(f"Validation accuracy improved from {best_val_acc:.2f}% to {val_accuracy:.2f}%")
            best_val_acc = val_accuracy
            best_model_state = model.state_dict()
            patience_counter = 0
        else:
            patience_counter += 1
            print(f"Validation accuracy did not improve. {patience-patience_counter} epochs until early stopping.")

        if patience_counter >= patience:
            print("\nEarly stopping triggered!")
            break

    # Restore best model
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
        print(f"\nRestored best model with validation accuracy: {best_val_acc:.2f}%")

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
        image = Image.open(image).convert("RGB")
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

    # Set dataset path
    dataset_path = "/mnt/h/Faces/StashDB_processed"

    parser = argparse.ArgumentParser(description="Train face recognition model")
    parser.add_argument("--source", type=str, default="stashdb", choices=["scene", "stashdb"],
                      help='Source type: "scene" or "stashdb"')
    args = parser.parse_args()

    # Train model with source type parameter
    model, classes = train_model(
        dataset_path,
        batch_size=32,
        num_epochs=50,
        learning_rate=0.001,
        log_file=str(log_path),
        source_type=args.source
    )

    # Save the model
    torch.save({
        "model_state_dict": model.state_dict(),
        "classes": classes,
        "timestamp": timestamp,
        "training_params": {
            "batch_size": 32,
            "learning_rate": 0.001,
            "architecture": "FaceNet + Custom Classifier",
            "dataset_path": dataset_path
        }
    }, model_path)

    print(f"\nTraining run {timestamp} completed:")
    print(f"Model saved to: {model_path}")
    print(f"Training log saved to: {log_path}")