/**
 * SwasthAI — the people whose records this account manages.
 * Records and medicines always belong to a profile: the account holder
 * ("Myself") or a family member. This helper loads those profiles and
 * lets the user create their own in one tap, so nobody is sent to the
 * Family page just to store their own prescription.
 */
const CareProfiles = (() => {
  function isSelf(member) {
    return (member.relationship || '').toLowerCase() === 'self';
  }

  function label(member) {
    return isSelf(member) ? `${member.name} (Myself)` : `${member.name} (${member.relationship})`;
  }

  // The user's own profile first, then family in the order they were added.
  async function list() {
    const members = await SwasthAPI.family.listMembers();
    return members.slice().sort((a, b) => Number(isSelf(b)) - Number(isSelf(a)));
  }

  async function addSelf() {
    const user = typeof swasthaiCurrentUser === 'function' ? swasthaiCurrentUser() : null;
    return SwasthAPI.family.createMember({
      name: (user && user.name) || 'Myself',
      relationship: 'Self'
    });
  }

  function optionsHtml(members, selectedId) {
    return members.map((m) =>
      `<option value="${AppUI.esc(m.id)}"${m.id === selectedId ? ' selected' : ''}>${AppUI.esc(label(m))}</option>`
    ).join('');
  }

  // Shown when the account has no profiles at all.
  function emptyStateHtml(what) {
    return AppUI.state({
      icon: 'fa-user-plus',
      title: 'Set up a profile first',
      text: `${what} are stored against a person. Add your own profile now, or add a family member from the Family page.`,
      actionHtml: `
        <div style="display:flex; gap: var(--sp-3); flex-wrap:wrap; justify-content:center;">
          <button type="button" class="btn btn-primary btn-compact" data-action="add-self"><i class="fas fa-user-check" aria-hidden="true"></i>&nbsp; Add my profile</button>
          <a class="btn btn-outline btn-compact" href="family.html">Add a family member</a>
        </div>`
    });
  }

  return { isSelf, label, list, addSelf, optionsHtml, emptyStateHtml };
})();
