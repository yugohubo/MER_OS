# MER_OS Core: Şirket Hafızası ve Orkestrasyon

Bu katman, tüm sistemlerin buluştuğu "Yönetici Dijital Zeka" merkezidir. **MER_OS v2**, LangChain veya CrewAI gibi hantal framework'ler yerine izole, tek sorumluluk prensibiyle (Single Responsibility) çalışan saf Python ajanlarına dayanır.

## Alt Ajanlar (Sub-Agents)

- 🗣️ **Orchestrator:** İnsan ile sistem arasındaki doğal dil arayüzüdür. "Human-in-the-Loop" (Kullanıcı Onayı) onay mekanizmasını devreye sokar.
- 💾 **Memory Curator (Hafıza Düzenleyici):** ChromaDB kullanarak vektörel arama yapar. Şirketin geçmiş dokümanlarını (örn: "Fabrika Analiz Raporu") ve **Solidworks BOM** dosyalarını hafızada tutar.
- 🔍 **Info Solver & 📝 Report Writer:** Verileri okur, süzgeçten geçirir ve kurumsal formata dökerek kaydeder.
- 💻 **Code Runner:** Anlık matematiksel simülasyonları ve betikleri (Analitik motorundaki Python kodları gibi) sandbox ortamında çalıştırır.

## İş Akışı Entegrasyonu (Nasıl Bağlanıyor?)

1. **BOM ve Fatura Yüklemesi:** Edge katmanındaki Solidworks BOM'ları (`.json`) ve satın alma faturaları **Memory Curator** tarafından ChromaDB'ye kaydedilir.
2. **Makine Anomalisi Gelir:** **Analytics Engine**'den (Analitik Motoru) "MTR-001 kodlu servo motorda vibrasyon anomalisi tespit edildi (PCA Z-Score > 3)" uyarısı gelir.
3. **Çapraz Eşleşme (RAG - Retrieval-Augmented Generation):**
   - *Orchestrator*, Memory Curator'a sorar: "MTR-001 parçası hangi projeye ait?"
   - *Memory Curator*, hafızayı tarar ve Solidworks BOM verisinden "PRJ-8472" projesini bulur.
   - *Orchestrator*, ERP ve depo çıkış zaman damgalarını kontrol eder.
4. **Çıktı / Uyarı:** Yöneticiye veya operatöre şu rapor sunulur: 
   > *"Dikkat: PRJ-8472 projesi için üretilen MTR-001 parçasını işleyen makinede anomali saptandı. Fire riski yüksek. İlgili operatör görevine 'Kök Neden Analizi' eklendi."*

Bu sayede sadece makine sağlığı takip edilmekle kalmaz; makinedeki arızanın **hangi projenin, hangi faturasını veya görev paketini** etkileyeceği tam otonom olarak bulunur.
