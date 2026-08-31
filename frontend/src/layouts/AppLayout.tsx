import { NavLink, Outlet } from 'react-router-dom';

import { useAuth } from '@/hooks/useAuth';

import styles from './AppLayout.module.css';

export function AppLayout(): JSX.Element {
  const { user, signOutUser } = useAuth();

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <span className={styles.brand}>Note Insight</span>

          <nav className={styles.nav}>
            <NavLink
              to="/notes/new"
              className={({ isActive }) => (isActive ? styles.linkActive : styles.link)}
            >
              New note
            </NavLink>
            <NavLink
              to="/notes"
              end
              className={({ isActive }) => (isActive ? styles.linkActive : styles.link)}
            >
              History
            </NavLink>
          </nav>

          <div className={styles.account}>
            <span className={styles.email}>{user?.email ?? ''}</span>
            <button
              type="button"
              className={styles.signOut}
              onClick={() => {
                void signOutUser();
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
