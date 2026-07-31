import { CheckCircle2, CircleAlert, Info, X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

type ToastKind = "success" | "error" | "info";
interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
}
interface ToastContextValue {
  showToast: (message: string, kind?: ToastKind) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);
  const timers = useRef(new Map<number, number>());

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer !== undefined) window.clearTimeout(timer);
    timers.current.delete(id);
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, kind: ToastKind = "info") => {
      const id = ++idRef.current;
      setToasts((current) => [...current, { id, message, kind }]);
      timers.current.set(id, window.setTimeout(() => dismiss(id), 4500));
    },
    [dismiss],
  );

  useEffect(() => () => {
    timers.current.forEach((timer) => window.clearTimeout(timer));
    timers.current.clear();
  }, []);

  const value = useMemo(() => ({ showToast }), [showToast]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-region" aria-live="polite" aria-label="Notifications">
        {toasts.map((toast) => {
          const Icon =
            toast.kind === "success" ? CheckCircle2 : toast.kind === "error" ? CircleAlert : Info;
          return (
            <div className={`toast toast-${toast.kind}`} key={toast.id} role="status">
              <Icon size={19} aria-hidden="true" />
              <span>{toast.message}</span>
              <button
                className="icon-button"
                onClick={() => dismiss(toast.id)}
                aria-label="Dismiss notification"
              >
                <X size={16} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}
