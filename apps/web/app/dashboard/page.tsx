import Link from 'next/link';
import { api } from '../../lib/api';
import { authConfigured } from '../../lib/auth0';
import { change } from './actions';
import styles from './workspace.module.css';

type Organization = { id: string; name: string; role: 'owner' | 'member' };
type Assessment = { id: string; title: string; description: string; status: 'draft' | 'archived' };
type Member = { user_id: string; role: 'owner' | 'member' };
type Params = Record<string, string | string[] | undefined>;

const feedback: Record<string, string> = {
  session: 'Your session expired. Sign in again.',
  forbidden: 'Only the organization owner can make that change.',
  missing: 'The requested record could not be found.',
  duplicate: 'That user already belongs to this organization.',
  invalid: 'Check the form fields and try again.',
  unavailable: 'The change could not be saved. Try again.',
};
const pageSize = 20;

export const dynamic = 'force-dynamic';

function Context({ organization, operation, item }: { organization?: string; operation: string; item?: string }) {
  return <>
    <input type="hidden" name="operation" value={operation} />
    {organization && <input type="hidden" name="organization" value={organization} />}
    {item && <input type="hidden" name="item" value={item} />}
  </>;
}

function AssessmentFields({ assessment }: { assessment?: Assessment }) {
  return <>
    <label>Title<input name="title" required maxLength={160} defaultValue={assessment?.title} /></label>
    <label>Description<textarea name="description" maxLength={4000} defaultValue={assessment?.description} /></label>
  </>;
}

export default async function Dashboard({ searchParams }: { searchParams: Promise<Params> }) {
  if (!authConfigured()) {
    return <main className={styles.shell}><h1>Workspace setup</h1>
      <p>Configure the Auth0 settings in the project README to sign in.</p><Link href="/">Return home</Link>
    </main>;
  }
  const query = await searchParams;
  const [profileResponse, orgResponse] = await Promise.all([api('/me'), api('/organizations')]);
  if (!profileResponse.ok || !orgResponse.ok) {
    return <main className={styles.shell}><h1>Workspace unavailable</h1>
      <p>Sign in again or retry in a moment.</p><a href="/auth/login">Sign in</a>
    </main>;
  }
  const profile: { id: string } = await profileResponse.json();
  const organizations: Organization[] = await orgResponse.json();
  const org = organizations.find(({ id }) => id === query.org) ?? organizations[0];
  const home = org ? '/dashboard?org=' + org.id : '/dashboard';
  const view = query.view === 'assessments' || query.view === 'settings' ? query.view : 'overview';
  const pageNumber = typeof query.page === 'string' ? Number(query.page) : 1;
  const page = Number.isSafeInteger(pageNumber) && pageNumber > 0 && pageNumber <= 100000 ? pageNumber : 1;
  const error = typeof query.error === 'string' && Object.hasOwn(feedback, query.error) ? feedback[query.error] : null;

  let assessments: Assessment[] = [];
  let selected: Assessment | undefined;
  let members: Member[] = [];
  let loadError = false;
  if (org && view === 'assessments') {
    const scope = '?organization_id=' + org.id;
    const item = typeof query.assessment === 'string' && /^[a-f0-9-]{36}$/i.test(query.assessment)
      ? query.assessment : null;
    const [list, record] = await Promise.all([
      api('/assessments' + scope + '&limit=' + (pageSize + 1) + '&offset=' + ((page - 1) * pageSize)),
      item ? api('/assessments/' + item + scope) : null,
    ]);
    if (list.ok) assessments = await list.json();
    if (record?.ok) selected = await record.json();
    loadError = !list.ok || Boolean(record && !record.ok);
  }
  if (org?.role === 'owner' && view === 'settings') {
    const roster = await api('/organizations/' + org.id + '/members');
    if (roster.ok) members = await roster.json();
    else loadError = true;
  }

  return <main className={styles.shell}>
    <header className={styles.header}>
      <div><span className={styles.brand}>AI Assurance</span><h1>{org?.name ?? 'Set up your workspace'}</h1></div>
      <a href="/auth/logout">Sign out</a>
    </header>
    <div className={styles.grid}>
      <aside>
        <section className={styles.card}>
          <h2>Organizations</h2>
          <ul>{organizations.map((entry) => <li key={entry.id}>
            <Link href={'/dashboard?org=' + entry.id} aria-current={entry.id === org?.id ? 'true' : undefined}>
              {entry.name}
            </Link>
          </li>)}</ul>
          <form action={change}>
            <Context operation="create-organization" />
            <label>New organization<input name="name" required maxLength={120} /></label>
            <button>Create organization</button>
          </form>
        </section>
      </aside>
      <div>
        {org && <nav className={styles.nav} aria-label="Workspace">
          <Link href={home} aria-current={view === 'overview' ? 'page' : undefined}>Overview</Link>
          <Link href={home + '&view=assessments'} aria-current={view === 'assessments' ? 'page' : undefined}>Assessments</Link>
          <Link href={home + '&view=settings'} aria-current={view === 'settings' ? 'page' : undefined}>Settings</Link>
        </nav>}
        {(error || loadError) && <p role="alert" className={styles.error}>{error ?? 'Some workspace data could not be loaded.'}</p>}
        {(!org || view === 'overview') && <section className={styles.card}>
          <h2>{org ? 'Workspace overview' : 'Create or join an organization'}</h2>
          <p>{org ? 'Start an assessment or return to a draft from the Assessments tab.'
            : 'Create an organization using the form, or share your account ID with an organization owner.'}</p>
          {!org && <p>Account ID <code>{profile.id}</code></p>}
          {org && <Link href={home + '&view=assessments'}>Manage assessments</Link>}
        </section>}
        {org && view === 'assessments' && <>
          <section className={styles.card}>
            <h2>Assessments</h2>
            {!assessments.length && !loadError && <p>No assessments on this page.</p>}
            <ul>{assessments.slice(0, pageSize).map((entry) => <li key={entry.id}>
              <Link href={home + '&view=assessments&page=' + page + '&assessment=' + entry.id}>{entry.title}</Link>
              <span className={styles.badge}>{entry.status}</span>
            </li>)}</ul>
            <div className={styles.nav}>
              {page > 1 && <Link href={home + '&view=assessments&page=' + (page - 1)}>Previous</Link>}
              {assessments.length > pageSize && <Link href={home + '&view=assessments&page=' + (page + 1)}>Next</Link>}
            </div>
          </section>
          {selected && <section className={styles.card} key={selected.id}>
            <h2>Edit assessment</h2>
            <form action={change}>
              <Context organization={org.id} operation="edit-assessment" item={selected.id} />
              <AssessmentFields assessment={selected} />
              <button>Save changes</button>
            </form>
            <form action={change}>
              <Context organization={org.id} item={selected.id}
                operation={selected.status === 'draft' ? 'archive-assessment' : 'restore-assessment'} />
              <button>{selected.status === 'draft' ? 'Archive assessment' : 'Restore draft'}</button>
            </form>
          </section>}
          <section className={styles.card}>
            <h2>New assessment</h2>
            <form action={change}>
              <Context organization={org.id} operation="create-assessment" />
              <AssessmentFields />
              <button>Create assessment</button>
            </form>
          </section>
        </>}
        {org && view === 'settings' && <section className={styles.card}>
          <h2>Settings</h2>
          <p>Account ID <code>{profile.id}</code></p>
          <p>Your role <strong>{org.role}</strong></p>
          {org.role === 'owner' && <>
            <form action={change}>
              <Context organization={org.id} operation="rename-organization" />
              <label>Organization name<input name="name" required maxLength={120} defaultValue={org.name} /></label>
              <button>Save name</button>
            </form>
            <h3>Members</h3>
            <ul>{members.map((member) => <li key={member.user_id}>
              <code>{member.user_id}</code> <span className={styles.badge}>{member.role}</span>
              {member.role === 'member' && <form action={change}>
                <Context organization={org.id} operation="remove-member" item={member.user_id} />
                <button>Remove member</button>
              </form>}
            </li>)}</ul>
            <form action={change}>
              <Context organization={org.id} operation="add-member" />
              <label>Account ID<input name="user_id" required maxLength={36} /></label>
              <button>Add member</button>
            </form>
          </>}
        </section>}
      </div>
    </div>
  </main>;
}
