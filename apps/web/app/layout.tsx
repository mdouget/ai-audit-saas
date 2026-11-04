import type { ReactNode } from 'react';
export const metadata = { title: 'AI Assurance', description: 'AI governance and risk assessment' };
export default function Layout({children}: {children: ReactNode}) {
  return <html lang="en"><body style={{margin:0,fontFamily:'system-ui, Arial',background:'#f6f8fb',color:'#17253c'}}>{children}</body></html>;
}
