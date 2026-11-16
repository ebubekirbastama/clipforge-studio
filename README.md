# ClipForge Studio — Short Studio

**Short Studio**, uzun videoları sosyal medya için kısa MP4 bölümlerine ayıran, Windows üzerinde çalışan masaüstü video işleme uygulamasıdır. CustomTkinter arayüzü üzerinden bölüm süresi, çıktı kalitesi, görüntü biçimi ve ses iyileştirme seçenekleri yönetilebilir.

> Uygulamanın arayüzünde görünen adı **SHORT STUDIO**'dur.

## ✨ Özellikler

- **Otomatik bölümleme:** Videoları 30, 45, 60, 90, 120 veya 180 saniyelik hedef sürelerle parçalara ayırır.
- **Akıllı kesim noktaları:** İsteğe bağlı sessizlik analizi yapar; FFmpeg'in `silencedetect` filtresiyle bulunan sessizliklerin yakınında kesim noktası seçmeye çalışır.
- **Dikey video çıktısı:** 9:16 formatında bulanık arka plan veya ortadan kırpma seçenekleri sunar.
- **Orijinal görüntü oranı:** Kaynağın en-boy oranını koruyan çıktı seçeneği bulunur.
- **Kalite profilleri:** Standart 1080p, yüksek kalite 1080p ve hızlı 720p seçenekleri vardır.
- **AI ses temizleme:** İsteğe bağlı Demucs `htdemucs` modeliyle insan sesini arka plan seslerinden ayırmayı dener.
- **Dip ses azaltma:** FFmpeg ses filtreleriyle sabit uğultu ve dip gürültüyü azaltma seçeneği sunar.
- **İlerleme ve işlem günlüğü:** Kodlama ve AI aşamalarının durumu arayüzde gösterilir.
- **İşlem iptali:** Devam eden FFmpeg işlemi durdurulabilir; tamamlanmış video parçaları korunur.
- **Otomatik çıktı klasörü:** Her işlem için kaynak dosya adı ve zaman damgası kullanılarak ayrı klasör oluşturulur.

## 🧰 Teknoloji kartları

| Teknoloji | Kullanım amacı |
|---|---|
| Python | Uygulama ve iş akışı |
| CustomTkinter | Modern masaüstü arayüzü |
| FFmpeg | Video kodlama, kesme, görüntü ve ses filtreleri |
| FFprobe | Video süresi, çözünürlük ve ses akışı bilgilerini okuma |
| Demucs / HTDemucs | İsteğe bağlı vokal/insan sesi ayrıştırma |
| PyTorch | Demucs modelinin çalıştırılması |
| SoundFile ve NumPy | WAV ses verisini okuma, yazma ve işleme |
| Tkinter | Dosya ve klasör seçme pencereleri |
| threading / queue | Arayüzü kilitlemeden arka plan işlemleri ve durum iletimi |

## 📁 Proje yapısı

```text
clipforge-studio/
├── short_bolucu.pyw   # Short Studio masaüstü uygulaması
├── KURULUM.bat        # Python paketlerinin kurulum betiği
└── Ciktilar/          # Varsayılan çıktı klasörü (ilk işlemde oluşturulur)
```

## 🚀 Kurulum

### Gereksinimler

- Windows
- Python ve pip
- İnternet bağlantısı (Python paketlerini kurmak ve Demucs modelini ilk kez indirmek için)
- FFmpeg ve FFprobe

### 1. Depoyu indirin

Projeyi ZIP olarak indirin veya Git ile klonlayın:

```bash
git clone https://github.com/ebubekirbastama/clipforge-studio.git
cd clipforge-studio
```

### 2. FFmpeg'i hazırlayın

Uygulamanın mevcut kaynak kodundaki `find_bin()` fonksiyonu FFmpeg ve FFprobe dosyalarını **C sürücüsünün kök dizininde** arar:

```text
C:\\ffmpeg.exe
C:\\ffprobe.exe
```

FFmpeg'i bu konumlara yerleştirin. Kurulum betiğinde `C:\\ffmpeg\\bin\\ffmpeg.exe` için de kontrol bulunmasına rağmen uygulamanın mevcut `find_bin()` fonksiyonu bu klasörü aramaz. Bu nedenle yalnızca kurulum betiğinin FFmpeg bulundu mesajını vermesi uygulamanın FFmpeg'i bulacağını garanti etmez.

FFmpeg otomatik olarak indirilmez veya kurulmaz.

### 3. Python paketlerini kurun

Proje klasöründeki `KURULUM.bat` dosyasını çalıştırın. Betik:

1. Python komutunun kullanılabilirliğini kontrol eder.
2. `customtkinter` paketini kurar/günceller.
3. `torch`, `demucs`, `soundfile` ve `numpy` paketlerini kurar.
4. C sürücüsünde FFmpeg için bazı konum kontrolleri yapar.

AI ses temizleme özelliği için PyTorch ve Demucs kurulumu büyük boyutlu olabilir.

## ▶️ Kullanım

1. `short_bolucu.pyw` dosyasını çift tıklayarak çalıştırın.
2. **Gözat** düğmesiyle kaynak video dosyasını seçin.
3. Bölüm süresini belirleyin.
4. Çıktı kalitesini ve görüntü biçimini seçin.
5. İhtiyacınıza göre akıllı kesim, AI ses temizleme veya dip ses azaltma seçeneklerini etkinleştirin.
6. İsterseniz çıktı klasörünü değiştirin.
7. **SHORT OLUŞTUR** düğmesine basın.
8. İşlem durumunu ilerleme çubuğundan ve işlem günlüğünden takip edin.

Desteklenen kaynak uzantıları: `.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`, `.m4v`.

## 🔍 Çalışma akışı

1. FFprobe ile kaynak videonun süresi, çözünürlüğü ve ses akışı kontrol edilir.
2. Akıllı kesim açıksa ve videoda ses varsa sessizlik noktaları analiz edilir.
3. Video süresi hedef bölüm süresine göre parçalara ayrılır; uygun aralıktaki en yakın sessizlik noktası kesim için tercih edilir.
4. Her çalışma için benzersiz bir çıktı klasörü oluşturulur.
5. Seçilen görüntü biçimi ve kalite profili uygulanarak bölümler MP4 olarak kodlanır.
6. AI ses temizleme açıksa, kaydedilmiş her parçanın sesi Demucs ile işlenir ve temizlenmiş ses videoya eklenmeye çalışılır.
7. Bölüm zamanları `bolum_zamanlari.txt` dosyasına yazılır.

## 🎞️ Çıktı profilleri

| Ayar | Uygulamadaki davranış |
|---|---|
| Standart · 1080p | 1080 × 1920 hedef boyut, H.264 CRF 23, veryfast |
| Yüksek kalite · 1080p | 1080 × 1920 hedef boyut, H.264 CRF 20, medium |
| Hızlı · 720p | 720 × 1280 hedef boyut, H.264 CRF 23, veryfast |
| Bulanık arka plan · 9:16 | Dikey tuval üzerinde bulanık arka plan ve ölçeklenmiş ön görüntü |
| Ortadan kırp · 9:16 | Görüntüyü dikey tuvale sığdırmak için ölçekleme ve merkezden kırpma |
| Orijinal görüntü oranı | Görüntü oranı korunur; yalnızca piksel en-boy oranı ayarlanır |

Kodlama çıktısı MP4, H.264 video ve mevcutsa AAC ses akışıdır. Ses için 192 kbit/s hedef bit hızı kullanılır.

## ⚠️ Teknik sınırlamalar ve notlar

- **FFmpeg yolu:** Mevcut `find_bin()` fonksiyonu yalnızca `C:\\ffmpeg.exe` ve `C:\\ffprobe.exe` dosyalarını arar. Arayüzde ve kurulum betiğinde belirtilen bazı alternatif klasörler fonksiyon tarafından aranmaz.
- **Akıllı kesim:** Sessizlik analizi yalnızca ses akışı bulunan videolarda yapılır. Kesim noktaları hedef sürelere yakın sessizliklere göre seçilir; konuşma veya sahne bütünlüğü garantisi vermez.
- **Bölüm süreleri:** Bölüm sayısı toplam süre ve hedef süreye göre hesaplanır; bölümler eşit aralıklara dağıtılır. Sessizlik noktaları bu aralıkları sınırlı ölçüde değiştirebilir.
- **AI ses temizleme:** İlk kullanımda modelin indirilmesi gerekebilir. PyTorch'un CUDA desteği kullanılabilir durumdaysa CUDA, değilse CPU seçilir. İşlem uzun sürebilir ve yüksek bellek/işlem gücü gerektirebilir.
- **AI hata yönetimi:** AI temizleme başarısız olursa tamamlanmış ham video korunur; ilgili parça için uyarı kaydedilir ve sonraki parçalar için AI temizleme devre dışı bırakılır.
- **Ses bulunmayan videolar:** AI ses temizleme seçeneği ses akışı olmayan videolarda çalışmaz.
- **İptal:** İptal sırasında tamamlanmış parçalar silinmez. O an kodlanan parça tamamlanmayabilir.
- **FFmpeg bağımlılığı:** FFmpeg ve FFprobe uygulamayla birlikte gelmez; ayrıca hazırlanmalıdır.
- **Platform:** Kod, Windows dosya yolları ve `os.startfile` davranışı temel alınarak hazırlanmıştır.

## 🔐 Güvenli kullanım

- Yalnızca düzenleme ve kullanma hakkına sahip olduğunuz video/ses dosyalarını işleyin.
- Kaynak videolarınızı ve oluşturulan çıktıları işlem öncesinde yedekleyin.
- Python paketlerini güvenilir kaynaklardan kurun.
- AI modelinin ilk indirilmesi için internet bağlantısı gerekebilir.

## 🛠️ Geliştirme notları

- FFmpeg yolu tek bir ayar üzerinden yapılandırılabilir hâle getirilebilir; kurulum betiği ile uygulama aynı konumları kontrol etmelidir.
- Bağımlılıklar sürüm aralıklarıyla bir `requirements.txt` dosyasında sabitlenebilir.
- İşlem geçmişi, ayrıntılı hata raporu ve çıktı dosyalarını arayüzden açma seçenekleri eklenebilir.

## 👨‍💻 Geliştirici

**Ebubekir Bastama**

- GitHub: [@ebubekirbastama](https://github.com/ebubekirbastama)
- Proje: [clipforge-studio](https://github.com/ebubekirbastama/clipforge-studio)
