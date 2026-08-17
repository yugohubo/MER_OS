# 🚀 MER_OS v2: Uçtan Uca Endüstriyel Zeka ve Veri Mimarisi

> **Proof of Work (İş Kanıtı):** Edge Computing ile sahadan toplanan makine verilerinin, fiziksel matematik denklemleriyle analiz edilip, CAD/BOM (Malzeme Listesi) dokümanlarıyla **MER_OS Yönetici Dijital Zekasında** nasıl otonom bir karara dönüştüğünü sergileyen uçtan uca sistem mimarisi.

---

## 🧭 1. Sistem Mimarisi ve Büyük Resim

Geleneksel fabrikalarda üretim sahası (OT), mühendislik (CAD) ve yönetim (ERP) birbirinden kopuktur. **MER_OS v2** bu siloları yıkarak tüm sistemi tek bir "Ajanik (Agentic) Hafıza" altında birleştirir.

Bütünleşik akış şu şekildedir:
1. **Edge Node (Uç Bilişim):** Sahadaki PLC'lerden yüksek frekanslı titreşim/akım verileri çekilir. Eş zamanlı olarak mühendislikten gelen Solidworks BOM'ları JSON'a çevrilerek sisteme beslenir.
2. **Analytics Engine (Analitik Motoru):** Karmaşık makine verileri saf fizik denklemleri (Lomb-Scargle, PCA, EMA) ile işlenerek "Sağlık Metrikleri"ne ve anomali uyarılarına dönüştürülür.
3. **MER_OS Core (Şirket Hafızası):** Makineden gelen anomali sinyali ile o an üretilen BOM parçası eşleştirilir. Sistem otonom olarak *hangi projenin gecikeceğini* saptar ve aksiyon alır.

---

## 🧠 2. MER_OS Çekirdeği (Core) ve Ajan Mimarisi

Sistemin kalbi olan MER_OS, LangChain gibi dışa bağımlı ve hantal framework'ler kullanmak yerine **saf Python** ile, *Hub & Spoke* (Merkez ve Dağıtık) ajan modelinde sıfırdan inşa edilmiştir.

### 🏛️ Mimari Şema

```text
                            ┌────────────────────────┐
                            │       KULLANICI        │
                            └───────────┬────────────┘
                                        │
                                        ▼
                  ┌───────────────────────────────────────────┐
                  │        🗣️ ARAYÜZ (ORCHESTRATOR) AJANI      │
                  │   • Kullanıcıyla doğal sohbet             │
                  │   • Niyet ve görev analizi (Intent)       │
                  │   • Alt ajanları delege etme & koordine   │
                  │   • Gelen sonuçları derleyip yanıtlama    │
                  └─────────────────────┬─────────────────────┘
                                        │
     ┌──────────────────┬───────────────┼───────────────┬──────────────────┐
     ▼                  ▼               ▼               ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌───────────┐ ┌───────────────┐ ┌────────────────┐
│ 🧠 BİLGİ     │ │ 📝 RAPOR     │ │ 💾 HAFIZA │ │ 💻 KOD/ARAÇ   │ │ (Gelecekte     │
│ ÇÖZÜCÜ       │ │ YAZICI       │ │ DÜZENLEYİCİ││ YAZICI        │ │ Yeni           │
│ (Info Solver)│ │ (Report      │ │ (Memory   │ │ (Code/Tool    │ │ Ajanlar)       │
│              │ │  Writer)     │ │  Curator) │ │  Synthesizer) │ │                │
└──────────────┘ └──────────────┘ └───────────┘ └───────────────┘ └────────────────┘
```

### 📂 MER_OS v2 Dizin Yapısı ve Gerçek Kodlar
Tüm sistem izole ve tek sorumluluk prensibiyle (Single Responsibility) çalışır:

- 📄 **Giriş Noktası:** [`mer_os_core/main.py`]
- 📂 **`mer_os_core/core/`**: Orkestratör ajan ve LLM istemcisinin bulunduğu merkez. İnsan-Onayı (Human-in-the-Loop) burada yönetilir.
- 📂 **`mer_os_core/agents/`**: Vektörel hafızayı tarayan *Memory Curator* ve veri ayıklayan *Info Solver* gibi spesifik alt ajanlar.
- 📂 **`mer_os_core/sandbox/`**: LLM'in güvenle dosya okuyup yazabildiği, Python betiklerini koşturabildiği izole üretim ortamı.

---

## 🏭 3. Edge Node: CAD'den JSON'a Köprü

Mühendislik departmanının tasarımlarını (Solidworks BOM) otomatik olarak MER_OS'un hafızasına besleyen sistemdir.

- 📄 **Betik Yolu:** [`edge_node/solid_to_json.py`]

Bu betik sayesinde, CAD dosyalarındaki parçalar, adetler ve ağırlıklar JSON'a çevrilip veritabanına atılır. **Böylece makinede bir arıza olduğunda, MER_OS o an HANGİ PROJENİN HANGİ PARÇASININ işlendiğini anında bilebilir.**

---

## 📈 4. Analitik Motor: Fizik ve İstatistiksel Analiz

Edge'den gelen yüksek frekanslı ham veriler doğrudan LLM'e verilmez. Önce matematiksel bir boru hattından (Pipeline) geçirilir.

- 📄 analytics_engine/machine_analytics_simulation.py

#### 🎯 Ağ Gecikmesinde Gerçek Frekans (Lomb-Scargle)
Endüstriyel ağlardaki Jitter (veri gecikmesi) standart FFT analizlerini bozar. **Lomb-Scargle** algoritması ile bu düzensiz zaman damgaları filtrelenerek makinenin gerçek titreşim frekansı kusursuz saptanır.

![Lomb-Scargle Analizi](/docs/assets/lomb_scargle_analysis.png)

#### 🚨 Çok Boyutlu Anomali Tespiti (PCA)
Sıcaklık, titreşim ve basınç gibi çok boyutlu veriler, kovaryans matrisinin özdeğer ayrışımı (PCA) ile 2 boyutlu Faz Uzayına indirgenir. Sistem, rulman bozulması gibi anomalileri görsel olarak ayırt eder.

![PCA Anomali Tespiti](/docs/assets/pca_anomaly_detection.png)

---

## 🎯 Sonuç ve Otonom Aksiyon (Use Case)

Tüm kodlar ve mimariler birleştiğinde, yönetici ekranında şu otonom senaryo gerçekleşir:

1. **Analitik Motor:** *"MTR-001 Servo motorunda yüksek titreşim (PCA Anomali) tespit edildi."*
2. **Memory Curator (Hafıza):** *"Solidworks BOM verisine göre MTR-001 şu an PRJ-8472 (Vibro-Press) projesi için üretiliyor."*
3. **Orchestrator:** Yöneticiye şu raporu gönderir:
   > ⚠️ **KRİTİK UYARI:** *PRJ-8472 projesi için üretilen MTR-001 parçasını işleyen makinede anomali saptandı. Proje teslimatında gecikme riski var. Stok kritik seviyede, satın alma veya bakım görevi otomatik açılsın mı? [Evet/Hayır]*

Bu mimari, şirketinizin veriyi sadece toplayan değil, onu anlayan ve **eyleme dönüştüren** gerçek bir organizmaya dönüşebileceğinin kanıtıdır.
