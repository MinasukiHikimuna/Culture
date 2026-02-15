import tensorflow as tf
import os

# Suppress TensorFlow logging
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

def test_gpu():
    print("\n1. TensorFlow Version:", tf.__version__)

    print("\n2. Available GPUs:", tf.config.list_physical_devices("GPU"))

    print("\n3. GPU Test:")
    try:
        with tf.device("/GPU:0"):
            # Create and multiply two matrices
            a = tf.random.normal([1000, 1000])
            b = tf.random.normal([1000, 1000])
            c = tf.matmul(a, b)
            # Force execution
            result = tf.reduce_sum(c)
            print("   Matrix multiplication successful")
            print("   Result shape:", c.shape)
            print("   Sum:", float(result))
    except Exception as e:
        print("   GPU test failed:", str(e))

if __name__ == "__main__":
    test_gpu() 