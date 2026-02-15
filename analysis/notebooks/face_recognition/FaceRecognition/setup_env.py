import logging
import os
import sys
import time
from pathlib import Path


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress TensorFlow logging
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

def setup_cuda_paths():
    """Setup CUDA paths for Windows"""
    if os.name != "nt":  # Only for Windows
        return

    # Common CUDA paths for version 12.8
    possible_cuda_paths = [
        # CUDA Toolkit paths
        "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.8\\bin",
        "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.8\\extras\\CUPTI\\lib64",
        "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.8\\include",
        # cuDNN paths
        "C:\\Program Files\\NVIDIA\\CUDNN\\v9.7.1\\bin",
        # NVIDIA driver paths
        "C:\\Program Files\\NVIDIA Corporation\\NVIDIA NvDLISR",
        "C:\\Windows\\System32\\DriverStore\\FileRepository\\nvgpu",
        os.path.expandvars("%CONDA_PREFIX%\\Library\\bin"),
    ]

    # Add paths if they exist
    for path in possible_cuda_paths:
        if Path(path).exists():
            try:
                os.add_dll_directory(path)
                logger.info(f"Added DLL directory: {path}")
            except Exception as e:
                logger.warning(f"Failed to add DLL directory {path}: {e}")

def setup_gpu():
    """Setup GPU configuration"""
    try:
        import tensorflow as tf

        # Log TensorFlow version
        logger.info(f"TensorFlow version: {tf.__version__}")

        # Get GPU devices
        gpus = tf.config.list_physical_devices("GPU")
        if not gpus:
            logger.warning("No GPU devices found!")
            return False

        logger.info(f"Found {len(gpus)} GPU(s):")
        for gpu in gpus:
            logger.info(f"  {gpu}")

        # Configure memory growth
        for gpu in gpus:
            try:
                tf.config.experimental.set_memory_growth(gpu, True)
                logger.info(f"Enabled memory growth for {gpu}")
            except RuntimeError as e:
                logger.warning(f"Error setting memory growth: {e}")

        # Enable mixed precision
        tf.keras.mixed_precision.set_global_policy("mixed_float16")
        logger.info("Enabled mixed precision training")

        # Test GPU computation
        logger.info("Testing GPU computation...")
        with tf.device("/GPU:0"):
            # More comprehensive GPU test
            a = tf.random.normal([1000, 1000])
            b = tf.random.normal([1000, 1000])
            start_time = time.time()
            c = tf.matmul(a, b)
            # Force execution by accessing result
            _ = c.numpy()
            end_time = time.time()
            logger.info(f"GPU matrix multiplication test completed in {end_time - start_time:.3f} seconds")

        return True

    except Exception as e:
        logger.error(f"Error setting up GPU: {e}")
        logger.error("Full exception:", exc_info=True)
        return False

# Setup CUDA paths first
setup_cuda_paths()

# Run GPU setup
if setup_gpu():
    logger.info("GPU setup successful")
else:
    logger.warning("GPU setup failed - falling back to CPU")

if __name__ == "__main__":
    # Additional diagnostics when run directly
    import tensorflow as tf

    print("\nSystem Information:")
    print(f"Python version: {sys.version}")
    print(f"OS: {os.name}")
    print(f"TensorFlow version: {tf.__version__}")

    print("\nGPU Information:")
    gpus = tf.config.list_physical_devices("GPU")
    print(f"Number of GPUs available: {len(gpus)}")
    for gpu in gpus:
        print(f"GPU device: {gpu}")

    print("\nEnvironment Variables:")
    relevant_vars = [
        "CUDA_PATH",
        "CUDA_VISIBLE_DEVICES",
        "PATH",
        "LD_LIBRARY_PATH",
        "PYTHONPATH"
    ]

    for var in relevant_vars:
        value = os.environ.get(var, "Not set")
        if var == "PATH":
            print(f"\nPATH entries:")
            for path in value.split(os.pathsep):
                if "cuda" in path.lower() or "nvidia" in path.lower():
                    print(f"  {path}")
        else:
            print(f"{var}: {value}")