import win32com.client
import pythoncom
import os
import json
from collections import defaultdict

def traverse_components(component, bom_counts):
    """Montaj ağacını özyinelemeli (recursive) tarar ve parça adetlerini sayar."""
    children = component.GetChildren
    if children:
        for child in children:
            comp_name = child.Name2
            # SolidWorks'ün parça sonuna eklediği "-1", "-2" gibi kopya numaralarını temizler
            if "-" in comp_name:
                comp_name = comp_name.rsplit('-', 1)[0]
            
            bom_counts[comp_name] += 1
            
            # Alt montajsa alt ağaca in
            traverse_components(child, bom_counts)

def process_assembly_folder(folder_path, output_json="malzeme_listesi_tablosu.json"):
    print(f"Başlatılıyor... Hedef Klasör: {folder_path}\n")

    sldasm_files = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.sldasm'):
                sldasm_files.append(os.path.join(root, file))

    if not sldasm_files:
        print("Klasörde hiç .SLDASM dosyası bulunamadı!")
        return

    print(f"Toplam {len(sldasm_files)} adet montaj bulundu. SolidWorks başlatılıyor...")

    try:
        swApp = win32com.client.Dispatch("SldWorks.Application")
        swApp.Visible = False
    except Exception as e:
        print(f"SolidWorks başlatılamadı: {e}")
        return

    swDocASSEMBLY = 2
    swOpenDocOptions_Silent = 1
    swOpenDocOptions_ReadOnly = 2

    structured_data = []

    for i, file_path in enumerate(sldasm_files, 1):
        assembly_name = os.path.basename(file_path)
        print(f"[{i}/{len(sldasm_files)}] İşleniyor: {assembly_name}")

        err_ptr = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warn_ptr = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)

        swModel = swApp.OpenDoc6(file_path, swDocASSEMBLY,
                                 swOpenDocOptions_Silent | swOpenDocOptions_ReadOnly,
                                 "", err_ptr, warn_ptr)

        if not swModel:
            print(f"  -> Hata: {assembly_name} açılamadı, atlanıyor.")
            continue

        if swModel.GetType == swDocASSEMBLY:
            swConf = swModel.ConfigurationManager.ActiveConfiguration
            swRootComp = swConf.GetRootComponent3(True)
            
            bom_counts = defaultdict(int)
            traverse_components(swRootComp, bom_counts)

            if bom_counts:
                # Malzeme listesini Key-Value liste formatına çeviriyoruz
                item_list = [
                    {"parca_adi": name, "adet": count}
                    for name, count in sorted(bom_counts.items(), key=lambda x: x[0])
                ]
                
                # Montaj ana kaydı
                assembly_record = {
                    "montaj_adi": assembly_name,
                    "dosya_yolu": file_path,
                    "toplam_parca_cesidi": len(bom_counts),
                    "toplam_parca_adedi": sum(bom_counts.values()),
                    "malzeme_listesi": item_list
                }
                
                structured_data.append(assembly_record)
            else:
                print(f"  -> Uyarı: {assembly_name} içi boş veya okunamadı.")

        swApp.CloseDoc(file_path)

    # Sonuçları JSON olarak kaydet
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(structured_data, f, ensure_ascii=False, indent=4)

    print(f"\nİşlem Tamamlandı! Tablo formatındaki veriler '{output_json}' dosyasına kaydedildi.")

if __name__ == "__main__":
    # KLASOR_YOLU = r"C:\Users.../Malzeme Listesi"  change this to relative
    process_assembly_folder(KLASOR_YOLU)