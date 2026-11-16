# -*- coding: utf-8 -*-
"""Short Studio - modern desktop video segmenter (Windows, CustomTkinter)."""
import json
import math
import os
import queue
import re
import subprocess
import threading
import tempfile
import shutil
import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

APP_NAME = 'SHORT STUDIO'
VIDEO_EXTS = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v'}
BG = '#0B1020'
CARD = '#141C2C'
CARD_ALT = '#192335'
BORDER = '#29364B'
TEXT = '#F3F6FC'
MUTED = '#96A5BB'
ACCENT = '#7C6CF5'
ACCENT_HOVER = '#6859D9'
SUCCESS = '#4CD6A5'
APP_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = APP_DIR / 'Ciktilar'


def find_bin(name):
    """Only use FFmpeg installed at root of C: (no PATH / local copies)."""
    choices = [Path('C:/') / f'{name}.exe',
               Path('C:/') / f'{name}.exe',
               Path('C:/') / f'{name}.exe']
    return next((str(p) for p in choices if p.is_file()), None)


def ffprobe_info(ffprobe, path):
    command = [ffprobe, '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,width,height',
               '-of', 'json', str(path)]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace',
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('Video bilgisi okunamadı: ' + result.stderr.strip()[:350])
    data = json.loads(result.stdout)
    duration = float(data.get('format', {}).get('duration', 0))
    stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
    if not stream or duration <= 0:
        raise ValueError('Geçerli video veya video süresi bulunamadı.')
    return duration, int(stream.get('width', 0)), int(stream.get('height', 0)), any(
        s.get('codec_type') == 'audio' for s in data.get('streams', []))


def plan_boundaries(duration, target, silence_centers=None):
    parts = max(1, math.ceil(duration / target))
    ideal = duration / parts
    silences = sorted(silence_centers or [])
    splits = [0.0]
    for i in range(1, parts):
        aim = ideal * i
        minimum_gap = max(4.0, ideal * 0.72)
        left = max(splits[-1] + minimum_gap, aim - min(8.0, target * .13))
        right = min(duration - (parts - i) * minimum_gap, aim + min(8.0, target * .13))
        nearby = [s for s in silences if left <= s <= right]
        splits.append(min(nearby, key=lambda s: abs(s-aim)) if nearby else aim)
    splits.append(duration)
    return [(splits[i], splits[i+1]) for i in range(parts)]


def detect_silences(ffmpeg, filename, duration, cancel, register_proc):
    command = [ffmpeg, '-hide_banner', '-nostdin', '-i', filename, '-af',
               'silencedetect=noise=-33dB:d=0.28', '-vn', '-f', 'null', '-']
    proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            text=True, encoding='utf-8', errors='replace',
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    register_proc(proc)
    details = proc.communicate()[1]
    if cancel.is_set():
        raise InterruptedError('İşlem iptal edildi.')
    starts = [float(x) for x in re.findall(r'silence_start:\s*([\d.]+)', details)]
    ends = [float(x) for x in re.findall(r'silence_end:\s*([\d.]+)', details)]
    if len(ends) < len(starts):
        ends.append(duration)
    return [(a + b) / 2 for a, b in zip(starts, ends) if b >= a]


def fmt_sec(value):
    total = int(value)
    return f'{total // 3600:02d}:{(total // 60) % 60:02d}:{total % 60:02d}'


class App(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode('dark')
        ctk.set_default_color_theme('blue')
        super().__init__()
        self.title('Short Studio | Profesyonel Video Bölücü')
        self.geometry('1180x800')
        self.minsize(490, 560)
        self.configure(fg_color=BG)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.current_proc = None
        self.busy = False
        self.source = tk.StringVar()
        self.destination = tk.StringVar(value=str(OUTPUT_ROOT))
        self.length = tk.StringVar(value='60 sn')
        self.orientation = tk.StringVar(value='Bulanık arka plan · 9:16')
        self.quality = tk.StringVar(value='Standart · 1080p')
        self.smart = tk.BooleanVar(value=True)
        self.ai_clean = tk.BooleanVar(value=False)
        self.denoise = tk.BooleanVar(value=False)
        self.ai_model = None
        self.ai_deps = None
        self.last_output = OUTPUT_ROOT
        self.compact_layout = None
        self.info = tk.StringVar(value='Henüz video seçilmedi')
        self.status = tk.StringVar(value='İşlem için hazır')
        self.parts = tk.StringVar(value='—')
        self.total_duration = tk.StringVar(value='—')
        self.progress_text = tk.StringVar(value='%0')
        self._layout()
        self.length.trace_add('write', lambda *_: self.refresh_estimate())
        self.after(120, self.poll)
        self.bind('<Configure>', self.on_resize)
        self.protocol('WM_DELETE_WINDOW', self.close)

    def label(self, parent, text, size=12, color=TEXT, bold=False, **kwargs):
        binding = {'textvariable': text} if isinstance(text, tk.Variable) else {'text': text}
        return ctk.CTkLabel(parent, **binding, text_color=color,
                            font=ctk.CTkFont(family='Segoe UI', size=size, weight='bold' if bold else 'normal'),
                            **kwargs)

    def card(self, parent):
        return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=18, border_width=1, border_color=BORDER)

    def section(self, parent, number, title, subtitle=None):
        header = ctk.CTkFrame(parent, fg_color='transparent')
        header.pack(fill='x', padx=23, pady=(21, 12))
        ctk.CTkLabel(header, text=number, width=34, height=34, corner_radius=11,
                     fg_color='#2C2A50', text_color='#BBB2FF',
                     font=ctk.CTkFont(size=13, weight='bold')).pack(side='left', padx=(0, 12))
        text_box = ctk.CTkFrame(header, fg_color='transparent')
        text_box.pack(side='left')
        self.label(text_box, title, 16, bold=True).pack(anchor='w')
        if subtitle:
            self.label(text_box, subtitle, 11, MUTED).pack(anchor='w')

    def _layout(self):
        shell = ctk.CTkFrame(self, fg_color='transparent')
        shell.pack(fill='both', expand=True, padx=14, pady=12)
        top = ctk.CTkFrame(shell, fg_color='transparent')
        top.pack(fill='x', pady=(0, 10))
        badge = ctk.CTkFrame(top, fg_color=ACCENT, width=52, height=52, corner_radius=15)
        badge.pack(side='left', padx=(0, 14))
        badge.pack_propagate(False)
        self.label(badge, '▶', 24, 'white', True).place(relx=.5, rely=.5, anchor='center')
        title_box = ctk.CTkFrame(top, fg_color='transparent')
        title_box.pack(side='left')
        self.label(title_box, 'SHORT STUDIO', 24, bold=True).pack(anchor='w')
        self.label(title_box, 'Videolarını kusursuz bölümlere dönüştür.', 12, MUTED).pack(anchor='w')
        # Kompakt ekranlarda genis baslik rozeti kullanilmaz.

        columns = ctk.CTkScrollableFrame(shell, fg_color='transparent', corner_radius=0,
                                     scrollbar_button_color='#354158')
        columns.pack(fill='both', expand=True)
        self.columns = columns
        left = ctk.CTkFrame(columns, fg_color='transparent')
        right = ctk.CTkFrame(columns, fg_color='transparent')
        self.left_panel, self.right_panel = left, right
        self.apply_responsive_layout(False)

        source_card = self.card(left)
        source_card.pack(fill='x', pady=(0, 15))
        self.section(source_card, '01', 'Kaynak video', 'Düzenlenecek medya dosyası')
        field = ctk.CTkFrame(source_card, fg_color='transparent')
        field.pack(fill='x', padx=23, pady=(0, 10))
        self.source_entry = ctk.CTkEntry(field, textvariable=self.source, placeholder_text='Bir video dosyası seçin…',
                                         fg_color='#0F1727', border_color=BORDER, height=44, corner_radius=11)
        self.source_entry.pack(side='left', fill='x', expand=True, padx=(0, 9))
        ctk.CTkButton(field, text='Gözat', width=91, height=44, corner_radius=11,
                      fg_color='#313E58', hover_color='#42526D', command=self.choose_video).pack(side='left')
        self.label(source_card, self.info, 11, MUTED, wraplength=360, justify='left').pack(anchor='w', padx=25, pady=(0, 22))

        settings_card = self.card(left)
        settings_card.pack(fill='x', pady=(0, 15))
        self.section(settings_card, '02', 'Video ayarları', 'Bölüm uzunluğu ve format')
        settings = ctk.CTkFrame(settings_card, fg_color='transparent')
        settings.pack(fill='x', padx=23, pady=(0, 18))
        settings.grid_columnconfigure((0, 1), weight=1, uniform='settings')
        self.label(settings, 'BÖLÜM SÜRESİ', 10, MUTED, True).grid(row=0, column=0, sticky='w', pady=(0, 7))
        self.label(settings, 'ÇIKTI KALİTESİ', 10, MUTED, True).grid(row=0, column=1, sticky='w', padx=(12, 0), pady=(0, 7))
        self.dropdown(settings, self.length, ['30 sn', '45 sn', '60 sn', '90 sn', '120 sn', '180 sn']).grid(
            row=1, column=0, sticky='ew')
        self.dropdown(settings, self.quality, ['Standart · 1080p', 'Yüksek kalite · 1080p', 'Hızlı · 720p']).grid(
            row=1, column=1, sticky='ew', padx=(12, 0))
        self.label(settings, 'GÖRÜNTÜ BİÇİMİ', 10, MUTED, True).grid(row=2, column=0, columnspan=2,
                                                                       sticky='w', pady=(18, 7))
        self.dropdown(settings, self.orientation, ['Bulanık arka plan · 9:16', 'Ortadan kırp · 9:16',
                                                     'Orijinal görüntü oranı']).grid(row=3, column=0, columnspan=2,
                                                                                     sticky='ew')
        toggle_wrap = ctk.CTkFrame(settings_card, fg_color=CARD_ALT, corner_radius=11)
        toggle_wrap.pack(fill='x', padx=23, pady=(0, 22))
        toggle_text = ctk.CTkFrame(toggle_wrap, fg_color='transparent')
        toggle_text.pack(side='left', fill='x', expand=True, padx=14, pady=12)
        self.label(toggle_text, 'Akıllı kesim noktaları', 12, bold=True).pack(anchor='w')
        self.label(toggle_text, 'Sessiz konuşma aralarında böl', 10, MUTED).pack(anchor='w')
        ctk.CTkSwitch(toggle_wrap, text='', variable=self.smart, width=44, progress_color=ACCENT,
                      button_color='white').pack(side='right', padx=(8, 12))

        audio_card = self.card(left)
        audio_card.pack(fill='x', pady=(0, 15))
        self.section(audio_card, '03', 'Ses temizleme', 'CUMHA AI Studio ses isleme teknolojisi')
        ai_box = ctk.CTkFrame(audio_card, fg_color=CARD_ALT, corner_radius=11)
        ai_box.pack(fill='x', padx=20, pady=(0, 10))
        ai_info = ctk.CTkFrame(ai_box, fg_color='transparent')
        ai_info.pack(side='left', fill='x', expand=True, padx=12, pady=10)
        self.label(ai_info, 'AI arka plan sesi temizle', 12, bold=True).pack(anchor='w')
        self.label(ai_info, 'Demucs ile insan sesini ortam sesinden ayir', 10, MUTED,
                   wraplength=260, justify='left').pack(anchor='w')
        ctk.CTkSwitch(ai_box, text='', variable=self.ai_clean, width=42,
                      progress_color=ACCENT).pack(side='right', padx=10)
        noise_box = ctk.CTkFrame(audio_card, fg_color=CARD_ALT, corner_radius=11)
        noise_box.pack(fill='x', padx=20, pady=(0, 20))
        noise_info = ctk.CTkFrame(noise_box, fg_color='transparent')
        noise_info.pack(side='left', fill='x', expand=True, padx=12, pady=10)
        self.label(noise_info, 'Dip ses / ugultu azalt', 12, bold=True).pack(anchor='w')
        self.label(noise_info, 'FFmpeg ile sabit hisirti ve ugultuyu azalt', 10, MUTED,
                   wraplength=260, justify='left').pack(anchor='w')
        ctk.CTkSwitch(noise_box, text='', variable=self.denoise, width=42,
                      progress_color=ACCENT).pack(side='right', padx=10)

        output_card = self.card(left)
        output_card.pack(fill='x', pady=(0, 8))
        self.section(output_card, '04', 'Çıktı konumu', 'Varsayılan: programın içindeki Ciktilar klasörü')
        out = ctk.CTkFrame(output_card, fg_color='transparent')
        out.pack(fill='x', padx=23, pady=(0, 22))
        ctk.CTkEntry(out, textvariable=self.destination, height=44, corner_radius=11,
                     fg_color='#0F1727', border_color=BORDER,
                     placeholder_text='Kaydetme klasörü').pack(side='left', fill='x', expand=True, padx=(0, 9))
        ctk.CTkButton(out, text='Seç', width=85, height=44, corner_radius=11,
                      fg_color='#313E58', hover_color='#42526D', command=self.choose_folder).pack(side='left')
        ctk.CTkButton(output_card, text='📂  Çıktı klasörünü aç', height=36, corner_radius=10,
                      fg_color='#313E58', hover_color='#42526D', command=self.open_output_folder).pack(
                          anchor='w', padx=23, pady=(0, 18))

        summary = self.card(right)
        summary.pack(fill='x', pady=(0, 15))
        self.label(summary, 'İŞLEM ÖZETİ', 11, MUTED, True).pack(anchor='w', padx=22, pady=(23, 9))
        self.label(summary, 'Hazır olduğunda başlat', 17, bold=True).pack(anchor='w', padx=22, pady=(0, 20))
        stats = ctk.CTkFrame(summary, fg_color='transparent')
        stats.pack(fill='x', padx=20, pady=(0, 19))
        for ix, (title, variable) in enumerate([('VİDEO SÜRESİ', self.total_duration), ('TAHMİNİ PARÇA', self.parts)]):
            unit = ctk.CTkFrame(stats, fg_color=CARD_ALT, corner_radius=12)
            unit.grid(row=0, column=ix, sticky='ew', padx=(0, 6) if ix == 0 else (6, 0))
            stats.grid_columnconfigure(ix, weight=1)
            self.label(unit, title, 10, MUTED, True).pack(anchor='w', padx=13, pady=(12, 3))
            self.label(unit, variable, 25, TEXT, True).pack(anchor='w', padx=13, pady=(0, 12))
        self.label(summary, 'İLERLEME', 10, MUTED, True).pack(anchor='w', padx=22)
        self.label(summary, self.progress_text, 22, bold=True).pack(anchor='e', padx=22, pady=(0, 6))
        self.bar = ctk.CTkProgressBar(summary, height=9, corner_radius=9, progress_color=ACCENT,
                                     fg_color='#30384B')
        self.bar.pack(fill='x', padx=22, pady=(0, 15))
        self.bar.set(0)
        self.label(summary, self.status, 11, MUTED, wraplength=310).pack(anchor='w', padx=22, pady=(0, 18))
        self.start_btn = ctk.CTkButton(summary, text='▶   SHORT OLUŞTUR', height=51, corner_radius=12,
                                       fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                       font=ctk.CTkFont(size=14, weight='bold'), command=self.start)
        self.start_btn.pack(fill='x', padx=22, pady=(0, 10))
        self.stop_btn = ctk.CTkButton(summary, text='İşlemi iptal et', height=39, corner_radius=11,
                                      fg_color='transparent', border_width=1, border_color=BORDER,
                                      text_color=MUTED, hover_color='#293348', command=self.stop, state='disabled')
        self.stop_btn.pack(fill='x', padx=22, pady=(0, 23))

        logcard = self.card(right)
        logcard.pack(fill='both', expand=True)
        self.label(logcard, 'İŞLEM GÜNLÜĞÜ', 11, MUTED, True).pack(anchor='w', padx=19, pady=(19, 9))
        self.logbox = ctk.CTkTextbox(logcard, fg_color='#0E1523', text_color='#C4D0DF',
                                     border_width=0, corner_radius=11,
                                     font=ctk.CTkFont(family='Consolas', size=11), state='disabled')
        self.logbox.pack(fill='x', padx=17, pady=(0, 17))
        self.logbox.configure(height=170)
        self.log('Short Studio başlatıldı. Video seçimi bekleniyor.')
        if not find_bin('ffmpeg') or not find_bin('ffprobe'):
            self.log('FFmpeg: C:\\ffmpeg\\bin veya C:\\ffmpeg içinde bulunamadı.')
        else:
            self.log('FFmpeg: C sürücüsündeki kurulum algılandı.')

        self.label(shell, 'SHORT STUDIO   •   WINDOWS   •   CUMHA AI + FFmpeg',
                   10, '#66778F').pack(anchor='w', pady=(8, 0))

    def apply_responsive_layout(self, compact):
        if not hasattr(self, 'columns'):
            return
        self.left_panel.grid_forget()
        self.right_panel.grid_forget()
        if compact:
            self.columns.grid_columnconfigure(0, weight=1)
            self.columns.grid_columnconfigure(1, weight=0)
            self.left_panel.grid(row=0, column=0, sticky='ew', padx=(0, 4), pady=(0, 14))
            self.right_panel.grid(row=1, column=0, sticky='ew', padx=(0, 4))
        else:
            self.columns.grid_columnconfigure(0, weight=7)
            self.columns.grid_columnconfigure(1, weight=4)
            self.left_panel.grid(row=0, column=0, sticky='new', padx=(0, 15))
            self.right_panel.grid(row=0, column=1, sticky='new', padx=(0, 4))
        self.compact_layout = compact

    def on_resize(self, event):
        if event.widget is not self:
            return
        compact = event.width < 930
        if compact != self.compact_layout:
            self.apply_responsive_layout(compact)

    def dropdown(self, parent, variable, values):
        return ctk.CTkOptionMenu(parent, variable=variable, values=values, height=43, corner_radius=10,
                                 fg_color='#233047', button_color='#34415C', button_hover_color='#465473',
                                 dropdown_fg_color='#233047', dropdown_hover_color='#394669',
                                 font=ctk.CTkFont(family='Segoe UI', size=12))

    def log(self, text):
        self.logbox.configure(state='normal')
        self.logbox.insert('end', f'›  {text}\n')
        self.logbox.see('end')
        self.logbox.configure(state='disabled')

    def refresh_estimate(self):
        path = self.source.get().strip()
        if not path or not Path(path).is_file():
            return
        ffprobe = find_bin('ffprobe')
        if not ffprobe:
            self.info.set('FFprobe bulunamadı: C:\\ffmpeg\\bin\\ffprobe.exe')
            return
        try:
            duration, w, h, _ = ffprobe_info(ffprobe, path)
            self.total_duration.set(fmt_sec(duration))
            self.parts.set(str(math.ceil(duration / int(self.length.get().split()[0]))))
            self.info.set(f'{Path(path).name}   ·   {w} × {h}   ·   {fmt_sec(duration)}')
        except Exception as exc:
            self.info.set(f'Video okunamadı: {exc}')

    def choose_video(self):
        path = filedialog.askopenfilename(title='Kaynak video seç',
            filetypes=[('Video dosyaları', '*.mp4 *.mov *.mkv *.avi *.webm *.m4v'), ('Tüm dosyalar', '*.*')])
        if path:
            self.source.set(path)
            self.refresh_estimate()
            self.log(f'Video seçildi: {Path(path).name}')

    def choose_folder(self):
        path = filedialog.askdirectory(title='Çıktı klasörü seç')
        if path:
            self.destination.set(path)

    def start(self):
        src = Path(self.source.get().strip())
        if not src.is_file() or src.suffix.lower() not in VIDEO_EXTS:
            messagebox.showerror('Kaynak video gerekli', 'Lütfen geçerli bir video dosyası seçin.')
            return
        folder = self.destination.get().strip()
        if not folder:
            messagebox.showerror('Çıktı klasörü gerekli', 'Lütfen çıktı klasörünü seçin.')
            return
        ffmpeg, ffprobe = find_bin('ffmpeg'), find_bin('ffprobe')
        if not ffmpeg or not ffprobe:
            messagebox.showerror('FFmpeg bulunamadı', 'FFmpeg ve FFprobe C sürücüsünde bulunamadı.\n\n'
                                 'Önerilen konumlar:\nC:\\ffmpeg\\bin\\ffmpeg.exe\n'
                                 'C:\\ffmpeg\\bin\\ffprobe.exe\n\n'
                                 'C:\\ffmpeg veya C:\\ kök dizini de desteklenir.')
            return
        self.cancel.clear()
        self.busy = True
        self.start_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.bar.set(0)
        self.progress_text.set('%0')
        self.log('— Yeni dönüştürme işlemi —')
        self.log('Çıktı ana klasörü: ' + folder)
        if self.ai_clean.get():
            self.log('AI açık: Önce her parçanın videosu kaydedilir, ardından sesi temizlenir.')
        options = (str(src), folder, int(self.length.get().split()[0]), self.orientation.get(),
                   self.quality.get(), self.smart.get(), self.ai_clean.get(), self.denoise.get(), ffmpeg, ffprobe)
        threading.Thread(target=self.worker, args=options, daemon=True).start()

    def register_proc(self, proc):
        self.current_proc = proc

    def prepare_ai_audio(self, ffmpeg, source, tempdir, duration):
        """Kaynak CUMHA AI Studio'daki htdemucs vokal ayirma akisinin uyarlamasi.

        Model bir kez yuklenir, 20 saniyelik bloklarla ses islenir; her iki
        yanda birer saniyelik baglam tutulur. Ayristirma kliplerden ONCE yapilir.
        """
        if self.ai_model is None:
            self.events.put(('status', 'AI modeli yükleniyor; ilk kullanımda internetten indirilebilir. Oluşturulmuş video klasörde duruyor…'))
            try:
                import numpy as np
                import soundfile as sf
                import torch
                from demucs.pretrained import get_model
            except ImportError as exc:
                raise RuntimeError('AI ses temizleme paketleri eksik. KURULUM.bat dosyasini calistirin. ' + str(exc))
            model = get_model('htdemucs')
            model.eval()
            self.ai_model = model
            self.ai_deps = (torch, sf, np)
        model = self.ai_model
        torch, sf, np = self.ai_deps
        raw = tempdir / 'source_audio.wav'
        vocal = tempdir / 'clean_voice.wav'
        self.events.put(('status', 'Ses AI islemine hazirlaniyor…'))
        self.run_command([ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                          '-i', source, '-vn', '-map', '0:a:0', '-ac', '2',
                          '-ar', str(model.samplerate), '-c:a', 'pcm_f32le', str(raw)])
        from demucs.apply import apply_model
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        with sf.SoundFile(str(raw), 'r') as source_wav:
            sr = int(source_wav.samplerate)
            chunk = 20 * sr
            context = sr
            n = len(source_wav)
            if n == 0:
                raise RuntimeError('Kaynak ses bos.')
            count = math.ceil(n / chunk)
            with sf.SoundFile(str(vocal), 'w', samplerate=sr, channels=2,
                              subtype='PCM_24') as result:
                for k in range(count):
                    if self.cancel.is_set():
                        raise InterruptedError('AI ses temizleme iptal edildi.')
                    start = k * chunk
                    stop = min(n, start + chunk)
                    begin = max(0, start - context)
                    end = min(n, stop + context)
                    source_wav.seek(begin)
                    audio = source_wav.read(end - begin, dtype='float32', always_2d=True)
                    tensor = torch.from_numpy(audio.T.copy())
                    mono = tensor.mean(dim=0)
                    mean = mono.mean()
                    std = mono.std().clamp(min=1e-8)
                    normalized = (tensor - mean) / std
                    with torch.no_grad():
                        stems = apply_model(model, normalized.unsqueeze(0), device=device,
                                            split=True, shifts=0, overlap=.25, progress=False)[0]
                    voice = (stems[model.sources.index('vocals')] * std + mean).cpu().numpy().T
                    offset = start - begin
                    result.write(np.clip(voice[offset:offset+(stop-start)], -1., 1.))
                    self.events.put(('status', f'AI arka plan temizleniyor · {k+1}/{count} ({device.upper()})'))
                    self.events.put(('ai_chunk', (k+1, count)))
        return vocal

    def run_command(self, command, duration=None, progress=None):
        """FFmpeg progress events without blocking the GUI or filling its pipe."""
        cmd = list(command)
        if progress is not None and duration and duration > 0:
            cmd[-1:-1] = ['-progress', 'pipe:1', '-nostats']
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace',
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.register_proc(proc)
        errors = []
        def read_errors():
            for line in proc.stderr:
                errors.append(line)
                if len(errors) > 80:
                    del errors[:20]
        reader = threading.Thread(target=read_errors, daemon=True)
        reader.start()
        try:
            for line in proc.stdout:
                if self.cancel.is_set():
                    proc.terminate()
                    raise InterruptedError('İşlem iptal edildi.')
                if progress is not None and line.startswith('out_time='):
                    try:
                        hrs, mins, secs = line.strip().split('=', 1)[1].split(':')
                        timevalue = int(hrs)*3600 + int(mins)*60 + float(secs)
                        progress(min(0.99, timevalue / duration))
                    except (ValueError, IndexError):
                        pass
            proc.wait()
            reader.join(timeout=2)
            if self.cancel.is_set():
                raise InterruptedError('İşlem iptal edildi.')
            if proc.returncode:
                raise RuntimeError('FFmpeg işlem hatası: ' + ''.join(errors)[-1800:])
            if progress is not None:
                progress(1.0)
            return ''.join(errors)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            if self.current_proc is proc:
                self.current_proc = None
            for stream in (proc.stdout, proc.stderr):
                if stream:
                    stream.close()

    def open_output_folder(self):
        folder = self.last_output if self.last_output.exists() else Path(self.destination.get().strip() or OUTPUT_ROOT)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if os.name == 'nt':
                os.startfile(str(folder))
            else:
                messagebox.showinfo('Çıktı klasörü', str(folder))
        except Exception as exc:
            messagebox.showerror('Klasör açılamadı', str(exc))

    @staticmethod
    def unique_job_dir(root, source):
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        basename = re.sub(r'[^\w\-]+', '_', Path(source).stem, flags=re.UNICODE).strip('_')[:65] or 'Video'
        for n in range(1, 1000):
            folder = root / (f'{basename}_{stamp}' + (f'_{n}' if n > 1 else ''))
            if not folder.exists():
                folder.mkdir(parents=True, exist_ok=False)
                return folder
        raise RuntimeError('Yeni çıktı klasörü oluşturulamadı.')

    def worker(self, source, output, target, orientation, quality, smart, ai_clean, denoise, ffmpeg, ffprobe):
        created = []
        warnings = []
        try:
            duration, w, h, has_audio = ffprobe_info(ffprobe, source)
            self.events.put(('log', f'Kaynak: {Path(source).name} | {fmt_sec(duration)} | {w}×{h}'))
            if smart and has_audio:
                self.events.put(('status', 'Sessizlik noktaları inceleniyor…'))
                silences = detect_silences(ffmpeg, source, duration, self.cancel, self.register_proc)
                self.events.put(('log', f'{len(silences)} sessizlik noktası bulundu.'))
            else:
                silences = []
            if ai_clean and not has_audio:
                raise RuntimeError('AI temizleme için ses içeren bir video seçin.')
            segments = plan_boundaries(duration, target, silences)
            outdir = self.unique_job_dir(Path(output), source)
            self.events.put(('output_dir', str(outdir)))
            self.events.put(('log', f'Klasör oluşturuldu: {outdir}'))
            profile = 'medium' if quality.startswith('Yüksek') else 'veryfast'
            crf = '20' if quality.startswith('Yüksek') else '23'
            width, height = (720, 1280) if quality.startswith('Hızlı') else (1080, 1920)
            if orientation.startswith('Bulanık'):
                vf = (f'[0:v]split=2[base][fg];[base]scale={width}:{height}:force_original_aspect_ratio=increase,'
                      f'crop={width}:{height},boxblur=18:4[bg];[fg]scale={width}:{height}:'
                      f'force_original_aspect_ratio=decrease[front];[bg][front]overlay=(W-w)/2:(H-h)/2,'
                      'setsar=1[vout]')
            elif orientation.startswith('Ortadan'):
                vf = (f'[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,'
                      f'crop={width}:{height},setsar=1[vout]')
            else:
                vf = '[0:v]setsar=1[vout]'
            manifest = []
            count = len(segments)
            for ix, (a, b) in enumerate(segments, 1):
                if self.cancel.is_set():
                    raise InterruptedError('İşlem iptal edildi.')
                outfile = outdir / f'{Path(source).stem}_PART_{ix:02d}.mp4'
                self.events.put(('status', f'PART {ix:02d}/{count} video kodlanıyor…'))
                self.events.put(('log', f'PART {ix:02d}  {fmt_sec(a)} → {fmt_sec(b)} ({b-a:.1f} sn)'))
                cmd = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                       '-ss', f'{a:.3f}', '-i', source, '-t', f'{b-a:.3f}',
                       '-filter_complex', vf, '-map', '[vout]']
                if has_audio:
                    cmd += ['-map', '0:a:0?']
                    if denoise and not ai_clean:
                        cmd += ['-af', 'highpass=f=75,afftdn=nf=-28:tn=1,alimiter=limit=0.95']
                    cmd += ['-c:a', 'aac', '-b:a', '192k']
                else:
                    cmd += ['-an']
                cmd += ['-c:v', 'libx264', '-preset', profile, '-crf', crf,
                        '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(outfile)]
                try:
                    self.run_command(cmd, duration=b-a, progress=lambda fraction, ix=ix:
                                     self.events.put(('progress', 100*((ix-1) + fraction*(0.35 if ai_clean else 1.0))/count)))
                except Exception:
                    outfile.unlink(missing_ok=True)
                    raise
                created.append(str(outfile))
                # The saved video already exists at this stage; AI operates on this short only.
                self.events.put(('log', f'✓ PART {ix:02d} video diske kaydedildi.'))
                self.events.put(('progress', ((ix-1) + (0.35 if ai_clean else 1.0)) / count * 100))
                if ai_clean:
                    self.events.put(('ai_part', (ix, count)))
                    try:
                        with tempfile.TemporaryDirectory(prefix='shortstudio_ai_') as td:
                            voice = self.prepare_ai_audio(ffmpeg, str(outfile), Path(td), b-a)
                            enhanced = Path(td) / 'enhanced.mp4'
                            command = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                                       '-i', str(outfile), '-i', str(voice), '-map', '0:v:0', '-map', '1:a:0',
                                       '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k']
                            if denoise:
                                command += ['-af', 'highpass=f=75,afftdn=nf=-28:tn=1,alimiter=limit=0.95']
                            command += ['-movflags', '+faststart', str(enhanced)]
                            self.events.put(('status', f'PART {ix}/{count} temizlenmiş ses kaydediliyor…'))
                            self.run_command(command)
                            if self.cancel.is_set():
                                raise InterruptedError('İşlem iptal edildi.')
                            os.replace(enhanced, outfile)
                            self.events.put(('log', f'✓ PART {ix:02d} AI sesiyle güncellendi.'))
                    except InterruptedError:
                        raise
                    except Exception as err:
                        # Never discard completed raw clips because of a model/dependency error.
                        warning = f'PART {ix:02d}: AI temizleme uygulanamadı ({str(err)[:200]}). Video korundu.'
                        warnings.append(warning)
                        self.events.put(('log', 'UYARI: ' + warning))
                        # A model/download failure is likely systemic; avoid retrying on every part.
                        ai_clean = False
                manifest.append(f'PART {ix:02d} | {fmt_sec(a)} - {fmt_sec(b)} | {b-a:.1f} saniye | {outfile.name}')
                (outdir / 'bolum_zamanlari.txt').write_text('\n'.join(manifest) + '\n', encoding='utf-8-sig')
                self.events.put(('progress', ix / count * 100))
                self.events.put(('status', f'{ix}/{count} video kaydedildi.'))
            self.events.put(('done', (len(created), str(outdir), warnings)))
        except InterruptedError:
            self.events.put(('error', 'İşlem iptal edildi. Tamamlanan videolar klasörde tutuldu.'))
        except Exception as exc:
            self.events.put(('error', f'{exc}\nTamamlanan dosyalar korunur.'))
        finally:
            self.current_proc = None
            self.events.put(('idle', None))

    def stop(self):
        if self.busy:
            self.cancel.set()
            proc = self.current_proc
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                except OSError:
                    pass
            self.status.set('İptal ediliyor…')

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'log':
                    self.log(value)
                elif kind == 'status':
                    self.status.set(value)
                elif kind == 'output_dir':
                    self.last_output = Path(value)
                elif kind == 'ai_part':
                    self._ai_progress_part = value
                elif kind == 'ai_chunk':
                    k, total = value
                    part, count = getattr(self, '_ai_progress_part', (1, 1))
                    self.bar.set(((part-1) + .35 + .60*k/max(1,total)) / count)
                    self.progress_text.set(f'%{100 * self.bar.get():.0f}')
                elif kind == 'progress':
                    self.bar.set(value / 100)
                    self.progress_text.set(f'%{value:.0f}')
                elif kind == 'error':
                    self.status.set('İşlem durduruldu')
                    self.log('UYARI: ' + value)
                    messagebox.showwarning('Short Studio', value)
                elif kind == 'done':
                    count, folder, warnings = value
                    self.status.set(f'Tamamlandı · {count} video oluşturuldu' + (f' · {len(warnings)} ses uyarısı' if warnings else ''))
                    self.log(f'Tamamlandı: {folder}')
                    if warnings:
                        messagebox.showwarning('Short Studio', f'{count} Short videosu oluşturuldu.\n\nAI ses temizlemede uyarı var; ilgili kliplerin orijinal sesleri korundu.\n\nKlasör:\n{folder}')
                    else:
                        messagebox.showinfo('Short Studio', f'{count} Short videosu hazır!\n\nKlasör:\n{folder}')
                elif kind == 'idle':
                    self.busy = False
                    self.start_btn.configure(state='normal')
                    self.stop_btn.configure(state='disabled')
        except queue.Empty:
            pass
        self.after(120, self.poll)

    def close(self):
        if self.busy:
            if not messagebox.askyesno('Programı kapat', 'İşlem sürüyor. İptal ederek çıkılsın mı?'):
                return
            self.stop()
        self.destroy()


if __name__ == '__main__':
    app = App()
    app.mainloop()
