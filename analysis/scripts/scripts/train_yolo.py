from ultralytics import YOLO
from pathlib import Path
import argparse
import yaml

def create_dataset_config(data_dir: str, classes: list) -> str:
    """
    Create YOLO dataset configuration file
    
    Args:
        data_dir (str): Path to dataset directory
        classes (list): List of class names
    
    Returns:
        str: Path to created config file
    """
    data_path = Path(data_dir)
    
    # Expected directory structure:
    # data_dir/
    #   ├── train/
    #   │   ├── images/
    #   │   └── labels/
    #   ├── val/
    #   │   ├── images/
    #   │   └── labels/
    #   └── test/
    #       ├── images/
    #       └── labels/
    
    config = {
        "path": str(data_path.absolute()),  # dataset root dir
        "train": "train/images",  # train images (relative to 'path')
        "val": "val/images",      # val images (relative to 'path')
        "test": "test/images",    # test images (optional)
        
        "names": {i: name for i, name in enumerate(classes)},  # class names
        "nc": len(classes)  # number of classes
    }
    
    # Save config file
    config_path = data_path / "dataset.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f, sort_keys=False)
    
    return str(config_path)

def train_model(data_config: str, epochs: int = 100, batch_size: int = 16, imgsz: int = 640):
    """
    Train YOLO model on custom dataset
    
    Args:
        data_config (str): Path to dataset config file
        epochs (int): Number of training epochs
        batch_size (int): Batch size
        imgsz (int): Image size
    """
    # Initialize model
    model = YOLO("yolo11n.pt")  # load pretrained model
    
    # Train the model
    results = model.train(
        data=data_config,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch_size,
        name="custom_model",  # experiment name
        exist_ok=True,        # overwrite existing experiment
        pretrained=True,      # start from pretrained model
        optimizer="auto",     # optimizer (SGD, Adam, etc.)
        verbose=True,         # print training progress
        device="auto"         # device to use (cuda device, i.e. 0 or 0,1,2,3 or cpu)
    )
    
    # Validate the model
    metrics = model.val()
    print("\nValidation Results:")
    print(f"mAP50: {metrics.box.map50:.3f}")
    print(f"mAP50-95: {metrics.box.map:.3f}")

def main():
    parser = argparse.ArgumentParser(description="Train YOLO model on custom dataset")
    parser.add_argument("data_dir", type=str, help="Path to dataset directory")
    parser.add_argument("--classes", nargs="+", required=True, help="List of class names")
    parser.add_argument("--epochs", type=int, default=100, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--img-size", type=int, default=640, help="Image size")
    
    args = parser.parse_args()
    
    # Create dataset config
    config_path = create_dataset_config(args.data_dir, args.classes)
    
    # Train model
    train_model(config_path, args.epochs, args.batch_size, args.img_size)

if __name__ == "__main__":
    main() 