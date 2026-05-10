import type React from 'react';
import { useEffect, useCallback } from 'react';
import { cn } from '../../utils/cn';

let activeDrawerCount = 0;

interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  width?: string;
  zIndex?: number;
  side?: 'left' | 'right';
  backdropClassName?: string;
  /** When true, disable all close mechanisms (backdrop click, Escape, close button). */
  disableClose?: boolean;
  /** When true, hide the built-in close (X) button in the header bar. */
  hideCloseButton?: boolean;
}

/**
 * Side drawer component with terminal-inspired styling.
 */
export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  title,
  children,
  width = 'max-w-2xl',
  zIndex = 50,
  side = 'right',
  backdropClassName,
  disableClose = false,
  hideCloseButton = false,
}) => {
  // Close the drawer when Escape is pressed (unless disabled).
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !disableClose) {
        onClose();
      }
    },
    [onClose, disableClose]
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      // Only lock body scroll for actual drawer mode (not full-screen)
      if (!disableClose) {
        activeDrawerCount++;
        if (activeDrawerCount === 1) {
          document.body.style.overflow = 'hidden';
        }
      }

      return () => {
        document.removeEventListener('keydown', handleKeyDown);
        if (!disableClose) {
          activeDrawerCount--;
          if (activeDrawerCount === 0) {
            document.body.style.overflow = '';
          }
        }
      };
    }
  }, [isOpen, handleKeyDown, disableClose]);

  if (!isOpen) return null;

  const titleId = title ? `drawer-title-${side}` : undefined;
  const sidePositionClass = side === 'left' ? 'left-0 justify-start' : 'right-0 justify-end';
  const borderClass = side === 'left' ? 'border-r' : 'border-l';
  // "full" → no max-width constraint (full-screen mode)
  const maxWidthClass = width === 'full' ? undefined : width;
  const isFullScreen = width === 'full';

  return (
    <div className="fixed inset-0 overflow-hidden" style={{ zIndex }} role="presentation">
      {/* Backdrop */}
      <div
        className={cn(
          'absolute inset-0 bg-background/80 backdrop-blur-sm transition-opacity duration-300',
          backdropClassName,
        )}
        onClick={disableClose ? undefined : onClose}
      />

      <div className={cn('absolute inset-y-0 flex w-full', sidePositionClass, maxWidthClass)}>
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          className={cn(
            'relative flex w-full flex-col bg-card',
            isFullScreen
              ? 'border-none shadow-none animate-none'
              : cn(
                  borderClass,
                  side === 'right' ? 'border-border/80' : 'border-border/70 shadow-2xl',
                  side === 'left' ? 'animate-slide-in-left' : 'animate-slide-in-right',
                ),
          )}
        >
          <div className={cn(
            'flex items-center border-b px-6 py-4',
            isFullScreen ? 'border-transparent' : 'border-border/60',
            title || !hideCloseButton ? 'justify-between' : 'justify-end',
          )}>
            {title ? (
              <div>
                <span className="label-uppercase">DETAIL VIEW</span>
                <h2 id={titleId} className="mt-1 text-lg font-semibold text-foreground">{title}</h2>
              </div>
            ) : null}
            {!hideCloseButton ? (
              <button
                type="button"
                onClick={onClose}
                className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border/70 bg-card/80 text-secondary-text transition-colors hover:bg-hover hover:text-foreground"
                aria-label="关闭抽屉"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            ) : null}
          </div>
          <div className="flex-1 overflow-y-auto p-6">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
};
