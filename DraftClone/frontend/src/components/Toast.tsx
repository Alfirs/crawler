type ToastProps = {
  message: string;
  kind?: 'info' | 'error';
};

const Toast = ({ message, kind = 'info' }: ToastProps) => (
  <div className={`toast ${kind}`}>{message}</div>
);

export default Toast;
