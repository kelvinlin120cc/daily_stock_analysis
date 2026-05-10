import type React from 'react';
import { useEffect, useState, useCallback } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { publicApi } from '../api/public';
import { Tooltip } from '../components/common/Tooltip';
import { getReportText, normalizeReportLanguage } from '../utils/reportLanguage';
import type { ReportLanguage } from '../types/analysis';
import { markdownToPlainText } from '../utils/markdown';
import { copyToClipboard } from '../utils/clipboard';

/**
 * Standalone share page — renders the full analysis report
 * without Shell, close button, or back navigation.
 * UI is identical to the full report view in ReportMarkdown.
 */
const SharePage: React.FC = () => {
  const { recordId } = useParams<{ recordId: string }>();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') ?? '';

  const id = recordId ? parseInt(recordId, 10) : NaN;

  const [stockName, setStockName] = useState('');
  const [stockCode, setStockCode] = useState('');
  const [reportLanguage, setReportLanguage] = useState<ReportLanguage>('zh');
  const [content, setContent] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedType, setCopiedType] = useState<'markdown' | 'text' | null>(null);
  const [shareLinkCopied, setShareLinkCopied] = useState(false);

  const text = getReportText(normalizeReportLanguage(reportLanguage));

  // Fetch report data
  useEffect(() => {
    if (isNaN(id) || !token) {
      setError('分享链接无效');
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    publicApi
      .getReportData(id, token)
      .then((data) => {
        if (cancelled) return;
        setStockName(data.stock_name ?? '');
        setStockCode(data.stock_code ?? '');
        setReportLanguage(data.report_language === 'en' ? 'en' : 'zh');
        setContent(data.markdown_content ?? '');
        setIsLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setError('分享链接已过期或无效，请联系分享者获取新的链接');
        setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id, token]);

  // Lock browser history — prevent back navigation on share page
  useEffect(() => {
    window.history.pushState({ share: true }, '', window.location.href);

    const handlePopState = (e: PopStateEvent) => {
      window.history.pushState({ share: true }, '', window.location.href);
    };

    window.addEventListener('popstate', handlePopState);

    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, []);

  // Handle share link copy
  const handleShare = useCallback(() => {
    const origin = window.location.origin;
    const url = `${origin}/share/${id}?token=${token}`;
    void copyToClipboard(url).then(ok => {
      if (ok) {
        setShareLinkCopied(true);
        setTimeout(() => setShareLinkCopied(false), 2000);
      }
    }).catch(() => {
      // Silent fail
    });
  }, [id, token]);

  // Handle copy markdown source
  const handleCopyMarkdown = useCallback(async () => {
    if (!content) return;
    const ok = await copyToClipboard(content);
    if (ok) {
      setCopiedType('markdown');
      setTimeout(() => setCopiedType(null), 2000);
    }
  }, [content]);

  // Handle copy plain text
  const handleCopyPlainText = useCallback(async () => {
    if (!content) return;
    const plainText = markdownToPlainText(content);
    const ok = await copyToClipboard(plainText);
    if (ok) {
      setCopiedType('text');
      setTimeout(() => setCopiedType(null), 2000);
    }
  }, [content]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-base">
        <div className="mx-auto max-w-3xl px-4 py-8">
          <div className="flex flex-col items-center justify-center py-32">
            <div className="home-spinner h-10 w-10 animate-spin border-[3px]" />
            <p className="mt-4 text-secondary-text text-sm">{text.loadingReport}</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-base">
        <div className="mx-auto max-w-md px-4 py-16">
          <div className="rounded-2xl border border-border/80 bg-card p-8 text-center shadow-lg">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-warning/10">
              <span className="text-2xl">⚠️</span>
            </div>
            <h2 className="mb-2 text-lg font-semibold text-foreground">分享链接无效</h2>
            <p className="text-sm text-secondary-text">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-base">
      <div className="mx-auto max-w-3xl px-4 py-6 sm:py-8">
        {/* Header — identical to ReportMarkdown */}
        <div className="flex items-center justify-between gap-3 mb-6">
          {/* Left: Icon + Title */}
          <div className="flex items-center gap-3 flex-1">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--home-action-report-bg)] text-[var(--home-action-report-text)]">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div>
              <h1 className="text-base font-semibold text-foreground">{stockName || stockCode}</h1>
              <p className="text-xs text-muted-text">{text.fullReport}</p>
            </div>
          </div>

          {/* Right: Toolbar */}
          <div className="flex items-center gap-2">
            {/* Share link button */}
            <Tooltip content="复制分享链接">
              <span className="inline-flex">
                <button
                  type="button"
                  onClick={handleShare}
                  disabled={isLoading || !content || shareLinkCopied}
                  className="home-surface-button flex h-10 w-10 items-center justify-center rounded-lg text-secondary-text hover:text-foreground disabled:opacity-50"
                  aria-label="复制分享链接"
                >
                  {shareLinkCopied ? (
                    <svg className="h-6 w-6 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                    </svg>
                  )}
                </button>
              </span>
            </Tooltip>

            {/* Copy Markdown button */}
            <Tooltip content={text.copyMarkdownSource}>
              <span className="inline-flex">
                <button
                  type="button"
                  onClick={handleCopyMarkdown}
                  disabled={isLoading || !content || copiedType !== null}
                  className="home-surface-button flex h-10 w-10 items-center justify-center rounded-lg text-secondary-text hover:text-foreground disabled:opacity-50"
                  aria-label={text.copyMarkdownSource}
                >
                  {copiedType === 'markdown' ? (
                    <svg className="h-6 w-6 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                  )}
                </button>
              </span>
            </Tooltip>

            {/* Copy plain text button */}
            <Tooltip content={text.copyPlainText}>
              <span className="inline-flex">
                <button
                  type="button"
                  onClick={handleCopyPlainText}
                  disabled={isLoading || !content || copiedType !== null}
                  className="home-surface-button flex h-10 w-10 items-center justify-center rounded-lg text-secondary-text hover:text-foreground disabled:opacity-50"
                  aria-label={text.copyPlainText}
                >
                  {copiedType === 'text' ? (
                    <svg className="h-6 w-6 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  )}
                </button>
              </span>
            </Tooltip>
          </div>
        </div>

        {/* Content — identical to ReportMarkdown */}
        <div
          className="home-markdown-prose prose prose-invert prose-sm max-w-none
            prose-headings:text-foreground prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-2
            prose-h1:text-xl
            prose-h2:text-lg
            prose-h3:text-base
            prose-p:leading-relaxed prose-p:mb-3 prose-p:last:mb-0
            prose-strong:text-foreground prose-strong:font-semibold
            prose-ul:my-2 prose-ol:my-2 prose-li:my-1
            prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none
            prose-pre:border
            prose-table:border-collapse
            prose-hr:my-4
            prose-a:no-underline hover:prose-a:underline
            prose-blockquote:text-secondary-text
            whitespace-pre-line break-words
          "
        >
          <Markdown remarkPlugins={[remarkGfm]}>
            {content}
          </Markdown>
        </div>
      </div>
    </div>
  );
};

export default SharePage;