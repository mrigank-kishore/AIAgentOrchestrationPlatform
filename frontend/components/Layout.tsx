import Link from 'next/link';
import { Bot, GitBranch, LayoutDashboard, Plug, Radio } from 'lucide-react';
import { useRouter } from 'next/router';
import type { ReactNode } from 'react';

const nav = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/agents', label: 'Agents', icon: Bot },
  { href: '/workflows', label: 'Workflows', icon: GitBranch },
  { href: '/integrations', label: 'Integrations', icon: Plug },
  { href: '/monitor', label: 'Monitor', icon: Radio },
];

export function Layout({ children }: { children: ReactNode }) {
  const router = useRouter();
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">AIAgentOrchestrationPlatform</div>
        <nav>
          {nav.map((item) => {
            const Icon = item.icon;
            const active = router.pathname === item.href;
            return (
              <Link key={item.href} className={`navItem ${active ? 'active' : ''}`} href={item.href}>
                <Icon size={18} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>
      <section className="content">{children}</section>
    </main>
  );
}
