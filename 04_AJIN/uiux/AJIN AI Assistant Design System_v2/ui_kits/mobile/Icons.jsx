// ui_kits/web_app/Icons.jsx — 1.5 stroke, 24x24, currentColor
const Icon = ({ d, size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: d }} />
);
const Icons = {
  Dashboard: (p) => <Icon {...p} d='<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>' />,
  Employee: (p) => <Icon {...p} d='<circle cx="11" cy="9" r="4"/><path d="M3 21c0-4 4-7 8-7s8 3 8 7"/><circle cx="19" cy="6" r="2"/>' />,
  Documents: (p) => <Icon {...p} d='<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>' />,
  Onboarding: (p) => <Icon {...p} d='<path d="M4 5h16v11H8l-4 4z"/><path d="M8 9h8M8 12h5"/>' />,
  Compliance: (p) => <Icon {...p} d='<path d="M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>' />,
  Admin: (p) => <Icon {...p} d='<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>' />,
  Equipment: (p) => <Icon {...p} d='<path d="M12 3l4 4-4 4-4-4z"/><path d="M12 11l4 4-4 4-4-4z"/><path d="M5 11l3 3-3 3-3-3z"/><path d="M19 11l3 3-3 3-3-3z"/>' />,
  Search: (p) => <Icon {...p} d='<circle cx="11" cy="11" r="6"/><path d="M16 16l5 5"/>' />,
  Send: (p) => <Icon {...p} d='<path d="M5 12l14-7-7 14-2-5z"/>' />,
  Lock: (p) => <Icon {...p} d='<rect x="5" y="11" width="14" height="9"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>' />,
  Profile: (p) => <Icon {...p} d='<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.5-7 8-7s8 3 8 7"/>' />,
  Logout: (p) => <Icon {...p} d='<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/>' />,
};
window.Icons = Icons;
