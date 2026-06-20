/* eslint-disable no-unused-vars */
const MOCK = {
  user: { email: 'yaakovpreiger@gmail.com', name: 'Yaakov', roles: ['admin', 'supervisor'] },
  admins: ['yaakovpreiger@gmail.com', 'valeria.preiger@gmail.com'],
  projects: [
    { id: 'p1', name: 'MedDevice QMS Audit 2025', standards: ['ISO9001', 'ISO13485'], status: 'mapping', progress: 72 },
    { id: 'p2', name: 'Environmental + OH&S Combined', standards: ['ISO14001', 'ISO45001'], status: 'findings', progress: 45 },
    { id: 'p3', name: 'ISO 9001 Surveillance', standards: ['ISO9001'], status: 'approved', progress: 100 },
  ],
  findings: [
    { id: 'f1', text: 'Document control procedure not consistently applied in production area.', status: 'pending', pairs: 2 },
    { id: 'f2', text: 'Training records for new operators incomplete for Q4 2024.', status: 'reviewed', pairs: 1 },
    { id: 'f3', text: 'Management review minutes missing action tracking for previous NCs.', status: 'pending', pairs: 3 },
  ],
  mappings: [
    { clause: '7.5', title: 'Documented information', relevance: 78, severity: 'major' },
    { clause: '7.2', title: 'Competence', relevance: 65, severity: 'minor' },
  ],
  isoClauses: {
    '4.1': {
      en: { title: 'Understanding the organization and its context', text: 'The organization shall determine external and internal issues that are relevant to its purpose and strategic direction.' },
      he: { title: 'הבנת הארגון והקשר שלו', text: 'הארגון יקבע נושאים חיצוניים ופנימיים הרלוונטיים למטרתו ולכיוון האסטרטגי שלו.' },
    },
    '5.1': {
      en: { title: 'Leadership and commitment', text: 'Top management shall demonstrate leadership and commitment with respect to the quality management system.' },
      he: { title: 'מנהיגות ומחויבות', text: 'ההנהלה הבכירה תפגין מנהיגות ומחויבות לגבי מערכת ניהול האיכות.' },
    },
    '7.5': {
      en: { title: 'Documented information', text: 'The organization shall control documented information required by the QMS and ISO 9001.' },
      he: { title: 'מידע מתועד', text: 'הארגון יבקר מידע מתועד הנדרש על ידי מערכת ניהול האיכות ו-ISO 9001.' },
    },
  },
  users: [
    { email: 'yaakovpreiger@gmail.com', name: 'Yaakov', roles: ['admin'] },
    { email: 'valeria.preiger@gmail.com', name: 'Valeria', roles: ['admin'] },
    { email: 'consultant@example.com', name: 'Consultant', roles: ['consultant'] },
  ],
  corpus: {
    iso: [{ name: 'ISO 9001:2015 EN', chunks: 842, status: 'Ready' }, { name: 'ISO 13485:2016 EN', chunks: 1204, status: 'Ready' }],
    samples: [{ name: '9001 - פירוט ממצאים.docx', chunks: 56, status: 'Ready' }],
    templates: [{ name: 'Combined report template (placeholder)', chunks: 0, status: 'Pending' }],
  },
  i18n: {
    en: {
      appTitle: 'ISO Compliance Platform',
      login: 'Sign in', logout: 'Sign out', projects: 'Projects', isoViewer: 'ISO Standards',
      knowledge: 'Knowledge', instructions: 'Instructions', users: 'Users', settings: 'Settings',
      mockBanner: 'Mock UI — static preview. Open index.html directly in your browser.',
      googleSignIn: 'Sign in with Google', devLogin: 'Continue as admin (mock)',
      newProject: 'New project', mapping: 'Mapping review', context: 'Context', findings: 'Findings',
      coverage: 'Coverage', exports: 'Exports', approve: 'Approve mapping', runAuto: 'Run auto-mapping',
      isoTitle: 'ISO text viewer', bilingual: 'Side by side', inviteUser: 'Invite user',
    },
    he: {
      appTitle: 'פלטפורמת תאימות ISO',
      login: 'התחברות', logout: 'יציאה', projects: 'פרויקטים', isoViewer: 'תקני ISO',
      knowledge: 'ידע', instructions: 'הנחיות', users: 'משתמשים', settings: 'הגדרות',
      mockBanner: 'ממשק דמו — תצוגה סטטית. פתחו index.html ישירות בדפדפן.',
      googleSignIn: 'התחברות עם Google', devLogin: 'המשך כמנהל (דמו)',
      newProject: 'פרויקט חדש', mapping: 'סקירת מיפוי', context: 'הקשר', findings: 'ממצאים',
      coverage: 'כיסוי', exports: 'ייצוא', approve: 'אישור מיפוי', runAuto: 'מיפוי אוטומטי',
      isoTitle: 'צפייה בטקסט ISO', bilingual: 'זו לצד זו', inviteUser: 'הזמנת משתמש',
    },
  },
};
