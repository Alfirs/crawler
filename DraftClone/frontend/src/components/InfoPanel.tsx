import { buildShareLink } from '../api/posts';
import { usePost } from '../state/useEditorStore';

type InfoPanelProps = {
  onSave: () => void;
  notify: (message: string, kind?: 'info' | 'error') => void;
};

const InfoPanel = ({ onSave, notify }: InfoPanelProps) => {
  const post = usePost();
  if (!post) return null;
  const shareLink = post.shareUrl ?? buildShareLink(post.id, post.token);

  const copyLink = () => {
    navigator.clipboard?.writeText(shareLink).then(
      () => notify('Link copied'),
      () => notify('Failed to copy', 'error')
    );
  };

  return (
    <section className="tab-panel">
      <p>ID поста: {post.id}</p>
      <p>Тема: {post.themeId}</p>
      <p>Статус: {post.status}</p>
      <div className="info-actions">
        <button type="button" onClick={onSave}>
          Save draft
        </button>
        <button type="button" onClick={() => window.open(shareLink, '_blank')}>
          Open link
        </button>
        <button type="button" onClick={copyLink}>
          Copy link
        </button>
      </div>
      <div className="share-row">
        <input value={shareLink} readOnly />
      </div>
    </section>
  );
};

export default InfoPanel;
