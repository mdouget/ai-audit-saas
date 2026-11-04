'use server';

import { redirect } from 'next/navigation';
import { api } from '../../lib/api';

const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;

export async function change(form: FormData) {
  const operation = form.get('operation');
  const org = String(form.get('organization') ?? '');
  const item = String(form.get('item') ?? '');
  const validOrg = uuid.test(org);
  const home = validOrg ? '/dashboard?org=' + org : '/dashboard';
  const assessment = '/assessments?organization_id=' + org;
  const record = '/assessments/' + item + '?organization_id=' + org;
  const members = '/organizations/' + org + '/members';
  const fields = { title: String(form.get('title') ?? ''), description: String(form.get('description') ?? '') };
  const name = String(form.get('name') ?? '');
  let response: Response;
  let destination = home;
  switch (operation) {
    case 'create-organization':
      response = await api('/organizations', 'POST', { name });
      if (response.ok) destination = '/dashboard?org=' + (await response.json()).id;
      break;
    case 'rename-organization':
      if (!validOrg) redirect(home);
      response = await api('/organizations/' + org, 'PATCH', { name });
      destination += '&view=settings';
      break;
    case 'add-member':
      if (!validOrg) redirect(home);
      response = await api(members, 'POST', { user_id: form.get('user_id') });
      destination += '&view=settings';
      break;
    case 'remove-member':
      if (!validOrg || !uuid.test(item)) redirect(home);
      response = await api(members + '/' + item, 'DELETE');
      destination += '&view=settings';
      break;
    case 'create-assessment':
      if (!validOrg) redirect(home);
      response = await api(assessment, 'POST', fields);
      destination += '&view=assessments';
      if (response.ok) destination += '&assessment=' + (await response.json()).id;
      break;
    case 'edit-assessment':
    case 'archive-assessment':
    case 'restore-assessment':
      if (!validOrg || !uuid.test(item)) redirect(home);
      response = await api(record, 'PATCH', operation === 'edit-assessment' ? fields : {
        status: operation === 'archive-assessment' ? 'archived' : 'draft',
      });
      destination += '&view=assessments&assessment=' + item;
      break;
    default:
      redirect(home);
  }
  if (!response.ok) {
    const feedback = { 401: 'session', 403: 'forbidden', 404: 'missing', 409: 'duplicate', 422: 'invalid' };
    destination += (destination.includes('?') ? '&' : '?') + 'error=' +
      (feedback[response.status as keyof typeof feedback] ?? 'unavailable');
  }
  redirect(destination);
}
