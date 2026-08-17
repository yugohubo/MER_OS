# Analitik Motor (Analytics Engine)

Edge PC'den alınan titreşim, akım ve sıcaklık gibi ham makine verileri, bu katmanda fiziksel ve istatistiksel denklemlerden geçirilerek anlamlı metrikler haline getirilir. 

Bu işlemler **Kestirimci Bakım (Predictive Maintenance)** ve anomali tespiti için hayati öneme sahiptir. İşlemleri `machine_analytics_simulation.py` betiği koşturur.

## Kullanılan Matematiksel ve İstatistiksel Formüller

### 1. Jitter ve Lomb-Scargle Periodogramı
Ağ gecikmelerinden (Jitter) dolayı zaman damgaları düzensizleştiğinde standart Hızlı Fourier Dönüşümü (FFT) hayalet frekanslar üretir. Bunun yerine **Lomb-Scargle** algoritması kullanılarak sinyaldeki gerçek frekanslar bulunur.
- *Bkz: Python betiği `simulate_and_plot_lomb_scargle()` fonksiyonu.*

### 2. Çok Boyutlu Sensör Anomalisi: Temel Bileşenler Analizi (PCA)
Sıcaklık, Basınç ve Titreşim verileri kovaryans matrisinin özdeğer ayrışımı ile 2 boyutlu Faz Uzayına (Phase Space) indirgenir. Böylece normal çalışma verisi ile makine yataklarındaki bozulmalar (anomali) görsel olarak ayrıştırılır.
- *Bkz: Python betiği `simulate_and_plot_pca()` fonksiyonu.*

### 3. Ek İstatistikler (Pipeline Arka Planı)
- **Varyans ve Standart Sapma:** Çevrim sürelerindeki sapmaları ölçer.
- **Üstel Hareketli Ortalama (EMA):** Geçmiş verilere azalan ağırlık vererek arıza trendini (trend smoothing) belirler.
- **Ayrık Türev:** Makine pozisyonundan hız ve ivme hesaplamalarına geçiş sağlar.

*Oluşturulan grafikler (Lomb-Scargle ve PCA) `docs/assets/` klasörüne otomatik kaydedilir ve ana raporlarda kullanılır.*
