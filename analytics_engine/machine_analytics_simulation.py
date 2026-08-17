import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import lombscargle
from sklearn.decomposition import PCA
import os

# Ensure the output directory exists
output_dir = "../docs/assets"
os.makedirs(output_dir, exist_ok=True)

def simulate_and_plot_lomb_scargle():
    """
    Simulates jittery (unevenly sampled) machine vibration data and applies 
    Lomb-Scargle Periodogram to find the true frequency without FFT ghosting.
    """
    print("[*] Running Lomb-Scargle Periodogram Simulation...")
    # True machine vibration frequency (e.g., 41.6 Hz for 2500 RPM)
    f_true = 41.6
    w_true = 2 * np.pi * f_true
    
    # Generate unevenly spaced time samples (Jitter simulation)
    np.random.seed(42)
    n_samples = 500
    t = np.sort(np.random.uniform(0, 1, n_samples))
    
    # Generate signal with some noise
    y = np.sin(w_true * t) + np.random.normal(0, 0.5, n_samples)
    
    # Frequencies to test
    f = np.linspace(10, 100, 1000)
    w = 2 * np.pi * f
    
    # Calculate Lomb-Scargle periodogram
    pgram = lombscargle(t, y, w, normalize=True)
    
    plt.figure(figsize=(10, 5))
    plt.subplot(1, 2, 1)
    plt.plot(t[:100], y[:100], 'o-', markersize=4, label='Jittery Data')
    plt.title('Time Domain (Jittery)')
    plt.xlabel('Time [s]')
    plt.ylabel('Amplitude')
    plt.legend()
    
    plt.subplot(1, 2, 2)
    plt.plot(f, pgram, color='red', label='Lomb-Scargle Power')
    plt.axvline(f_true, color='black', linestyle='--', label=f'True Freq: {f_true} Hz')
    plt.title('Frequency Domain (Lomb-Scargle)')
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Normalized Power')
    plt.legend()
    
    plt.tight_layout()
    plot_path = os.path.join(output_dir, "lomb_scargle_analysis.png")
    plt.savefig(plot_path)
    plt.close()
    print(f"[+] Saved {plot_path}")

def simulate_and_plot_pca():
    """
    Simulates multi-dimensional sensor data (Temp, Vibration, Pressure) and 
    reduces it using PCA to detect anomalies in a 2D Phase Space.
    """
    print("[*] Running PCA Anomaly Detection Simulation...")
    np.random.seed(42)
    
    # Normal operation data (Cluster 1)
    normal_temp = np.random.normal(45, 2, 200)
    normal_vib = np.random.normal(1.2, 0.1, 200)
    normal_press = np.random.normal(100, 5, 200)
    
    # Anomalous operation data (Cluster 2 - Bearing degradation)
    anom_temp = np.random.normal(60, 4, 50)
    anom_vib = np.random.normal(2.5, 0.4, 50)
    anom_press = np.random.normal(95, 8, 50)
    
    # Combine data
    temp = np.concatenate([normal_temp, anom_temp])
    vib = np.concatenate([normal_vib, anom_vib])
    press = np.concatenate([normal_press, anom_press])
    
    X = np.column_stack((temp, vib, press))
    
    # Normalize data
    X_mean = np.mean(X, axis=0)
    X_std = np.std(X, axis=0)
    X_norm = (X - X_mean) / X_std
    
    # Apply PCA
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_norm)
    
    plt.figure(figsize=(8, 6))
    plt.scatter(X_pca[:200, 0], X_pca[:200, 1], c='blue', alpha=0.6, label='Normal Operation')
    plt.scatter(X_pca[200:, 0], X_pca[200:, 1], c='red', alpha=0.8, marker='x', label='Anomaly Detected')
    plt.title('PCA Phase Space - Multi-Sensor Anomaly Detection')
    plt.xlabel(f'Principal Component 1 ({pca.explained_variance_ratio_[0]*100:.1f}%)')
    plt.ylabel(f'Principal Component 2 ({pca.explained_variance_ratio_[1]*100:.1f}%)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plot_path = os.path.join(output_dir, "pca_anomaly_detection.png")
    plt.savefig(plot_path)
    plt.close()
    print(f"[+] Saved {plot_path}")

if __name__ == "__main__":
    simulate_and_plot_lomb_scargle()
    simulate_and_plot_pca()
    print("[*] Analytics simulation complete.")
