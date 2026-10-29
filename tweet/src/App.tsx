import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import html2canvas from 'html2canvas';
import {
  BarChart2,
  Bookmark,
  CheckCircle2,
  Download,
  Heart,
  Image as ImageIcon,
  MessageSquare,
  Repeat,
  Sparkles,
  Upload,
} from 'lucide-react';

const OUTPUT_WIDTH = 1200;
const OUTPUT_HEIGHT = 900;

export default function App() {
  const [profileName, setProfileName] = useState('بسیج دانشجویی دانشگاه خواجه نصیر');
  const [handle, setHandle] = useState('@BorhanKntu');
  const [tweetText, setTweetText] = useState(
    'عاقبت سرسپرده بودن و نداشتن #استقلال به جایی خواهد رسید که در کشور مسلمان اجرای قوانین اسلام ممنوع خواهد شد.\nآقای علیف از سرنوشت رضاخانها بترس که عاقبتی جز مردن در خفت و خواری در انتظار دیکتاتورهای وابسته نیست.',
  );
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [backgroundUrl, setBackgroundUrl] = useState<string | null>(null);
  const [mediaUrl, setMediaUrl] = useState<string | null>(null);
  const [includeMedia, setIncludeMedia] = useState(false);
  const [cardBlur, setCardBlur] = useState(8);
  const [cardOpacity, setCardOpacity] = useState(65);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState('');

  const previewRef = useRef<HTMLDivElement | null>(null);
  const avatarInputRef = useRef<HTMLInputElement | null>(null);
  const backgroundInputRef = useRef<HTMLInputElement | null>(null);
  const mediaInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    return () => {
      if (avatarUrl) URL.revokeObjectURL(avatarUrl);
    };
  }, [avatarUrl]);

  useEffect(() => {
    return () => {
      if (backgroundUrl) URL.revokeObjectURL(backgroundUrl);
    };
  }, [backgroundUrl]);

  useEffect(() => {
    return () => {
      if (mediaUrl) URL.revokeObjectURL(mediaUrl);
    };
  }, [mediaUrl]);

  const handleImageUpload = (
    event: ChangeEvent<HTMLInputElement>,
    setImage: (url: string | null) => void,
  ) => {
    const file = event.target.files?.[0];
    if (file) setImage(URL.createObjectURL(file));
    event.target.value = '';
  };

  const renderTweetText = (text: string) =>
    text.split(/(#[\w_\u0600-\u06FF]+)/g).map((part, index) =>
      part.startsWith('#') ? (
        <span key={index} className="text-[#1d9bf0] font-medium">
          {part}
        </span>
      ) : (
        <span key={index}>{part}</span>
      ),
    );

  const downloadImage = async () => {
    const preview = previewRef.current;
    if (!preview) {
      setDownloadError('پیش‌نمایش تصویر در دسترس نیست. صفحه را دوباره بارگذاری کنید.');
      return;
    }

    setIsDownloading(true);
    setDownloadError('');

    try {
      await document.fonts.ready;
      const bounds = preview.getBoundingClientRect();
      const card = preview.querySelector<HTMLElement>('[data-tweet-card]');
      if (!card) throw new Error('Tweet card element is unavailable');
      const cardBounds = card.getBoundingClientRect();

      const backgroundCanvas = await html2canvas(preview, {
        backgroundColor: null,
        scale: 1,
        useCORS: true,
        logging: false,
        ignoreElements: (element) => element === card,
      });
      const blurredBackground = document.createElement('canvas');
      blurredBackground.width = backgroundCanvas.width;
      blurredBackground.height = backgroundCanvas.height;
      const backgroundContext = blurredBackground.getContext('2d');
      if (!backgroundContext) throw new Error('Background canvas context is unavailable');
      backgroundContext.filter = `blur(${cardBlur}px)`;
      backgroundContext.drawImage(backgroundCanvas, 0, 0);
      backgroundContext.filter = 'none';
      backgroundContext.fillStyle = `rgba(0, 0, 0, ${cardOpacity / 100})`;
      backgroundContext.fillRect(0, 0, blurredBackground.width, blurredBackground.height);
      const blurredBackgroundUrl = blurredBackground.toDataURL('image/png');

      const canvas = await html2canvas(preview, {
        backgroundColor: null,
        scale: OUTPUT_WIDTH / bounds.width,
        useCORS: true,
        logging: false,
        onclone: (clonedDocument) => {
          const clonedCard = clonedDocument.querySelector<HTMLElement>('[data-tweet-card]');
          if (!clonedCard) throw new Error('Tweet card clone is unavailable');

          clonedCard.style.backgroundColor = 'transparent';
          clonedCard.style.backdropFilter = 'none';
          clonedCard.style.setProperty('-webkit-backdrop-filter', 'none');
          clonedCard.style.overflow = 'hidden';

          const backdrop = clonedDocument.createElement('img');
          backdrop.src = blurredBackgroundUrl;
          backdrop.alt = '';
          Object.assign(backdrop.style, {
            position: 'absolute',
            left: `${bounds.left - cardBounds.left}px`,
            top: `${bounds.top - cardBounds.top}px`,
            width: `${bounds.width}px`,
            height: `${bounds.height}px`,
            maxWidth: 'none',
            zIndex: '0',
            pointerEvents: 'none',
          });
          clonedCard.insertBefore(backdrop, clonedCard.firstChild);
          Array.from(clonedCard.children).forEach((child) => {
            if (child !== backdrop && child instanceof HTMLElement) {
              child.style.position = 'relative';
              child.style.zIndex = '1';
            }
          });
        },
      });

      const output = document.createElement('canvas');
      output.width = OUTPUT_WIDTH;
      output.height = OUTPUT_HEIGHT;
      const context = output.getContext('2d');
      if (!context) throw new Error('Canvas context is unavailable');
      context.drawImage(canvas, 0, 0, OUTPUT_WIDTH, OUTPUT_HEIGHT);

      const image = await new Promise<Blob>((resolve, reject) => {
        output.toBlob((blob) => {
          if (blob) resolve(blob);
          else reject(new Error('PNG export failed'));
        }, 'image/png');
      });
      const imageUrl = URL.createObjectURL(image);
      const link = document.createElement('a');
      link.href = imageUrl;
      link.download = 'tweet-1200x900.png';
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(imageUrl), 1000);
    } catch (error) {
      console.error('Tweet image download failed:', error);
      setDownloadError('دانلود تصویر انجام نشد. لطفاً دوباره تلاش کنید.');
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
      <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-900/90 px-4 py-4 backdrop-blur-md sm:px-6">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-cyan-500 via-blue-600 to-indigo-600 text-lg font-bold text-white shadow-lg shadow-cyan-500/20">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight text-white sm:text-lg">
                توییت‌نوشت
              </h1>
              <p className="text-xs text-slate-400">ساخت و دانلود تصویر توییت</p>
            </div>
          </div>
          <button
            type="button"
            onClick={downloadImage}
            disabled={isDownloading}
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-cyan-950/30 transition hover:bg-cyan-500 disabled:cursor-wait disabled:opacity-60"
          >
            <Download className="h-4 w-4" />
            {isDownloading ? 'در حال آماده‌سازی…' : 'دانلود تصویر'}
          </button>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-6 p-4 sm:p-6 lg:grid-cols-12">
        <section className="space-y-4 lg:col-span-5" aria-label="تنظیمات توییت">
          <div className="space-y-5 rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-white">
                <ImageIcon className="h-4 w-4 text-cyan-400" />
                ساخت توییت
              </h2>
              <span className="rounded-md border border-cyan-800/50 bg-cyan-950/60 px-2 py-1 text-[11px] text-cyan-300">
                خروجی ۴:۳
              </span>
            </div>

            <div className="space-y-4">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-slate-300">نام پروفایل</span>
                <input
                  type="text"
                  value={profileName}
                  onChange={(event) => setProfileName(event.target.value)}
                  className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none transition focus:border-cyan-500"
                  dir="rtl"
                />
              </label>

              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-slate-300">آیدی / یوزرنیم</span>
                <input
                  type="text"
                  value={handle}
                  onChange={(event) => setHandle(event.target.value)}
                  className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none transition focus:border-cyan-500"
                  dir="ltr"
                />
              </label>

              <label className="block">
                <span className="mb-1.5 flex items-center justify-between text-xs font-medium text-slate-300">
                  <span>متن توییت</span>
                  <span className="text-[11px] font-normal text-cyan-400">هشتگ‌ها خودکار رنگی می‌شوند</span>
                </span>
                <textarea
                  rows={6}
                  value={tweetText}
                  onChange={(event) => setTweetText(event.target.value)}
                  className="w-full resize-y rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm leading-7 text-white outline-none transition focus:border-cyan-500"
                  dir="rtl"
                />
              </label>
            </div>

            <div className="grid grid-cols-1 gap-3 border-t border-slate-800 pt-4 sm:grid-cols-2">
              <div>
                <span className="mb-2 block text-[11px] text-slate-400">تصویر پروفایل</span>
                <button
                  type="button"
                  onClick={() => avatarInputRef.current?.click()}
                  className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 px-3 py-2.5 text-xs text-slate-200 transition hover:bg-slate-700"
                >
                  <Upload className="h-4 w-4 text-cyan-400" />
                  {avatarUrl ? 'تغییر تصویر' : 'انتخاب تصویر'}
                </button>
                <input
                  ref={avatarInputRef}
                  type="file"
                  accept="image/*"
                  onChange={(event) => handleImageUpload(event, setAvatarUrl)}
                  className="hidden"
                />
              </div>
              <div>
                <span className="mb-2 block text-[11px] text-slate-400">تصویر پس‌زمینه</span>
                <button
                  type="button"
                  onClick={() => backgroundInputRef.current?.click()}
                  className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 px-3 py-2.5 text-xs text-slate-200 transition hover:bg-slate-700"
                >
                  <Upload className="h-4 w-4 text-cyan-400" />
                  {backgroundUrl ? 'تغییر تصویر' : 'انتخاب تصویر'}
                </button>
                <input
                  ref={backgroundInputRef}
                  type="file"
                  accept="image/*"
                  onChange={(event) => handleImageUpload(event, setBackgroundUrl)}
                  className="hidden"
                />
              </div>
            </div>

            <div className="flex items-center justify-between border-t border-slate-800 pt-4">
              <div>
                <span className="block text-xs font-medium text-slate-300">تصویر ضمیمه</span>
                <span className="mt-1 block text-[11px] text-slate-500">نمایش تصویر داخل توییت</span>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => mediaInputRef.current?.click()}
                  className="text-xs text-cyan-400 transition hover:text-cyan-300"
                >
                  {mediaUrl ? 'تغییر تصویر' : 'انتخاب تصویر'}
                </button>
                <input
                  ref={mediaInputRef}
                  type="file"
                  accept="image/*"
                  onChange={(event) => {
                    handleImageUpload(event, setMediaUrl);
                    setIncludeMedia(true);
                  }}
                  className="hidden"
                />
                <button
                  type="button"
                  role="switch"
                  aria-checked={includeMedia}
                  aria-label="نمایش تصویر ضمیمه"
                  onClick={() => setIncludeMedia((shown) => !shown)}
                  className={`flex h-5 w-9 items-center rounded-full p-1 transition ${
                    includeMedia ? 'justify-end bg-cyan-600' : 'justify-start bg-slate-700'
                  }`}
                >
                  <span className="h-3 w-3 rounded-full bg-white shadow" />
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 border-t border-slate-800 pt-4 sm:grid-cols-2">
              <label>
                <span className="mb-2 flex justify-between text-xs text-slate-400">
                  <span>تیرگی کارت</span>
                  <span className="font-mono text-cyan-400">{cardOpacity}%</span>
                </span>
                <input
                  type="range"
                  min="30"
                  max="95"
                  value={cardOpacity}
                  onChange={(event) => setCardOpacity(Number(event.target.value))}
                  className="w-full accent-cyan-500"
                />
              </label>
              <label>
                <span className="mb-2 flex justify-between text-xs text-slate-400">
                  <span>تاری شیشه</span>
                  <span className="font-mono text-cyan-400">{cardBlur}px</span>
                </span>
                <input
                  type="range"
                  min="0"
                  max="20"
                  value={cardBlur}
                  onChange={(event) => setCardBlur(Number(event.target.value))}
                  className="w-full accent-cyan-500"
                />
              </label>
            </div>
          </div>

          <div className="flex items-start gap-3 rounded-xl border border-emerald-900/50 bg-emerald-950/20 p-4 text-xs leading-6 text-slate-300">
            <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-emerald-400" />
            <p>تصویر توییت با فرمت PNG و اندازهٔ ثابت ۱۲۰۰×۹۰۰ پیکسل دانلود می‌شود.</p>
          </div>
        </section>

        <section className="lg:col-span-7" aria-label="پیش‌نمایش توییت">
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4 shadow-lg sm:p-5">
            <div className="mb-4 flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-white">
                <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-cyan-400" />
                پیش‌نمایش زنده
              </h2>
              <span className="font-mono text-xs text-slate-400">۱۲۰۰ × ۹۰۰</span>
            </div>

            <div className="flex min-h-[300px] items-center justify-center overflow-hidden rounded-xl border border-slate-800 bg-slate-950 p-3 sm:min-h-[420px]">
              <div
                ref={previewRef}
                id="tweet-image-preview"
                className="relative flex aspect-[4/3] w-full max-w-[640px] items-center justify-center overflow-hidden rounded-xl shadow-2xl"
                style={{
                  backgroundImage: backgroundUrl
                    ? `url("${backgroundUrl}")`
                    : 'linear-gradient(135deg, #1e1b4b 0%, #0f172a 50%, #030712 100%)',
                  backgroundSize: 'cover',
                  backgroundPosition: 'center',
                  border: '1px solid rgba(51, 65, 85, 0.6)',
                  color: '#f1f5f9',
                }}
              >
                <div className="absolute inset-0" style={{ backgroundColor: 'rgba(0, 0, 0, 0.45)' }} />
                <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.04)_0,transparent_100%)]" />
                <div className="absolute left-4 top-4 z-10 opacity-70">
                  <svg className="h-5 w-5 fill-white" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                  </svg>
                </div>

                <article
                  className="relative z-10 flex w-[88%] max-w-[520px] gap-3 rounded-xl p-4 text-right shadow-2xl sm:gap-4 sm:p-5"
                  data-tweet-card
                  dir="rtl"
                  style={{
                    backgroundColor: `rgba(0, 0, 0, ${cardOpacity / 100})`,
                    backdropFilter: `blur(${cardBlur}px)`,
                    WebkitBackdropFilter: `blur(${cardBlur}px)`,
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                  }}
                >
                  <div className="shrink-0">
                    {avatarUrl ? (
                      <img
                        src={avatarUrl}
                        alt=""
                        className="h-9 w-9 rounded-full object-cover sm:h-11 sm:w-11"
                        style={{ border: '1px solid rgba(255, 255, 255, 0.3)' }}
                      />
                    ) : (
                        <div
                          className="flex h-9 w-9 items-center justify-center rounded-full text-xs font-bold shadow sm:h-11 sm:w-11"
                          style={{
                            backgroundImage: 'linear-gradient(45deg, #06b6d4, #4f46e5)',
                            border: '1px solid rgba(255, 255, 255, 0.3)',
                            color: '#ffffff',
                          }}
                        >
                          BK
                        </div>
                    )}
                  </div>

                  <div className="flex min-w-0 flex-1 flex-col gap-2">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-xs font-bold sm:text-sm" style={{ color: '#ffffff' }}>
                        {profileName}
                      </span>
                      <span
                        className="font-mono text-[10px] sm:text-xs"
                        style={{ color: '#94a3b8' }}
                        dir="ltr"
                      >
                        {handle}
                      </span>
                    </div>

                    <p
                      className="break-words whitespace-pre-line text-[11px] font-normal leading-relaxed sm:text-[13px]"
                      style={{ color: '#ffffff' }}
                    >
                      {renderTweetText(tweetText)}
                    </p>

                    {includeMedia && mediaUrl && (
                      <div
                        className="my-1 flex w-full items-center justify-center overflow-hidden rounded-xl border"
                        style={{ borderColor: 'rgba(255, 255, 255, 0.15)' }}
                      >
                        <img
                          src={mediaUrl}
                          alt="تصویر ضمیمه"
                          className="block h-auto w-full object-contain"
                        />
                      </div>
                    )}

                    <div
                      className="mt-1 flex items-center justify-between border-t pt-2"
                      style={{ borderColor: 'rgba(255, 255, 255, 0.1)', color: '#94a3b8' }}
                    >
                      <MessageSquare className="h-3.5 w-3.5" aria-label="پاسخ" />
                      <Repeat
                        className="h-3.5 w-3.5"
                        style={{ color: 'rgba(52, 211, 153, 0.9)' }}
                        aria-label="بازنشر"
                      />
                      <Heart
                        className="h-3.5 w-3.5"
                        style={{ color: 'rgba(236, 72, 153, 0.9)' }}
                        aria-label="پسند"
                      />
                      <BarChart2 className="h-3.5 w-3.5" aria-label="بازدید" />
                      <Bookmark className="h-3.5 w-3.5" aria-label="ذخیره" />
                    </div>
                  </div>
                </article>
              </div>
            </div>

            {downloadError && (
              <p role="alert" className="mt-3 text-sm text-rose-400">
                {downloadError}
              </p>
            )}

            <button
              type="button"
              onClick={downloadImage}
              disabled={isDownloading}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-wait disabled:opacity-60"
            >
              <Download className="h-4 w-4" />
              {isDownloading ? 'در حال آماده‌سازی تصویر…' : 'دانلود تصویر توییت'}
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
