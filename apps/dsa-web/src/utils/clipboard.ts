/**
 * Cross-platform clipboard utility.
 * Tries the modern Clipboard API first, then falls back to the
 * legacy execCommand('copy') approach that works on mobile browsers
 * (including Android Chrome, Samsung Internet, etc.).
 */

/**
 * Copy text to clipboard with mobile-browser fallback.
 * Returns true on success, false on failure.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  // 1. Try modern Clipboard API (requires secure context / HTTPS)
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // fall through to fallback
    }
  }

  // 2. Fallback: create a temporary <textarea>, select its content, and exec copy
  return new Promise<boolean>((resolve) => {
    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      // Prevent scrolling to bottom on mobile
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      textarea.style.top = '-9999px';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);

      // On mobile, selection may need focus
      textarea.focus();
      textarea.select();
      textarea.setSelectionRange(0, textarea.value.length);

      const success = document.execCommand('copy');
      document.body.removeChild(textarea);
      resolve(success);
    } catch {
      resolve(false);
    }
  });
}
