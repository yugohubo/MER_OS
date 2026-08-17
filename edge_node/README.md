# Edge Bilişim ve Veri Toplama Merkezi (Edge Node)

Endüstriyel sahadaki PLC sistemlerinden yüksek frekanslı verilerin toplanması ve ERP (Solidworks) sistemlerinden BOM (Malzeme Listesi) verilerinin çekilmesi bu katmanda gerçekleşir.

## 1. Makine Verisi Toplama (Telemetri)

Geleneksel EtherNet/IP sorgu-cevap (Explicit Messaging) yöntemlerindeki **Jitter (Ağ Gecikmesi)** sorununu aşmak için özel bir **AAR (After Action Report) Protokolü** geliştirilmiştir:

- **Örnekleme Hızı:** Nyquist kuralı gereği minimum 1 kHz (saniyede 1000 örnek).
- **Array Mantığı:** PLC, sensör verisini kendi içinde 1000 elemanlı bir diziye yazar.
- **Python Edge Çekimi:** Edge PC'deki Python betiği, saniyede sadece 1 kez (1 Hz) ağa çıkarak bu ~4 KB'lık bloğu tek seferde çeker. Bant genişliği korunur, Jitter sıfırlanır.

## 2. Mühendislik Verisi (Solidworks BOM) Çekimi

Makineden gelen fiziksel verilerin projelerle eşleşebilmesi için, mühendislik departmanının ürettiği CAD dosyalarındaki malzeme listelerinin (BOM) sayısallaştırılması gerekir.

Bu işlemi simüle eden `solidworks_bom_extractor.py` betiği, Solidworks (.SLDASM) dosyalarını tarar ve parça listesini, adetlerini ve ağırlıklarını JSON formatına çevirerek **MER_OS** hafızasına gönderilmeye hazır hale getirir.

### Örnek JSON Çıktısı:
```json
{
  "ProjectID": "PRJ-8472",
  "Assembly": "Vibro_Press_V2.SLDASM",
  "TotalParts": 4,
  "BOM": [
    {
      "PartNumber": "MTR-001",
      "Description": "Ana Servo Motor",
      "Quantity": 2
    }
  ]
}
```
