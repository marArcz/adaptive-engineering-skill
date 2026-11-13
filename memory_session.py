"""Read-only session activation and explicitly requested capture-mode changes."""
from __future__ import annotations

import argparse
import json

from memory_capture import _capture_lock, _policy
from memory_context import build_context
from memory_setup import POLICY, set_capture
from memory_store import _safe
from vault_guard import capture_gate
from _vault_common import resolve_vault


def activate(vault=None, *, current_instructions='', max_chars=12000, max_notes=1500):
    """Load only general bootstrap context; eligibility never proves a future save."""
    result = {'status': 'unavailable', 'context': '', 'capture_mode': 'unavailable',
              'capture_eligible': False, 'persistence_verified': False,
              'scope': 'active_skill_session_only'}
    try:
        vault = resolve_vault(str(vault) if vault is not None else None)
        if vault is None:
            return dict(result, reason='vault_not_configured')
        if not vault.is_dir():
            return dict(result, reason='vault_missing_or_inaccessible')
        context = build_context(vault, current_instructions=current_instructions,
                                max_chars=max_chars, max_excerpts=0, max_notes=max_notes)
        result.update(context)
        result['status'] = 'recall_only' if context['memory_incomplete'] else 'ready'
        try:
            _safe(vault, vault / POLICY)
            policy = _policy(vault)
        except (OSError, ValueError, TypeError, KeyError):
            return dict(result, status='recall_only', reason='invalid_or_inaccessible_capture_settings')
        result['capture_mode'] = policy['capture']
        result['boundaries'] = policy['boundaries']
        gate = capture_gate(vault)
        result['merge_state'] = gate.state
        if policy['capture'] == 'paused':
            return dict(result, reason='capture_paused')
        if not gate.allowed:
            return dict(result, reason='merge_gate_blocked')
        if all(value == 'exclude' for value in policy['boundaries'].values()):
            return dict(result, reason='all_capture_categories_excluded')
        if context['memory_incomplete'] or any(context['scan_limits'][key] for key in
                ('invalid_files', 'conflicted_records', 'unreadable_files', 'unsafe_links', 'oversized_files')):
            return dict(result, reason='capture_evidence_incomplete')
        return dict(result, capture_eligible=True, reason='capture_enabled_writes_still_require_verification')
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return dict(result, status='unavailable', capture_eligible=False, reason='session_context_unavailable')


def change_capture(mode, vault=None, *, user_requested=False, skill_active=False):
    """Preserve other policy fields, serialize the change and verify its readback."""
    result = {'status': 'unavailable', 'announcement': '', 'may_have_written': False}
    if user_requested is not True or skill_active is not True:
        return dict(result, status='excluded', reason='direct_user_request_and_active_skill_required')
    try:
        if mode not in ('active', 'paused'):
            raise ValueError('unsupported capture mode')
        vault = resolve_vault(str(vault) if vault is not None else None)
        if vault is None or not vault.is_dir():
            return dict(result, reason='vault_missing_or_unconfigured')
        if not capture_gate(vault).allowed:
            return dict(result, reason='merge_gate_blocked')
        with _capture_lock(vault):
            _safe(vault, vault / POLICY)
            before = _policy(vault)
            if before['capture'] == mode:
                return dict(result, status='unchanged', capture_mode=mode)
            if not capture_gate(vault).allowed:
                return dict(result, reason='merge_gate_blocked')
            result['may_have_written'] = True
            set_capture(vault, mode)
            _safe(vault, vault / POLICY)
            if _policy(vault) != dict(before, capture=mode):
                raise ValueError('capture settings changed during update')
            return dict(result, status='updated', capture_mode=mode,
                        announcement='Memory capture paused.' if mode == 'paused' else
                                     'Memory capture enabled for active skill sessions.')
    except BlockingIOError:
        return dict(result, status='busy', reason='memory_operation_in_progress')
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError):
        return dict(result, reason='capture_mode_change_unverified')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault')
    parser.add_argument('--action', choices=('activate', 'pause', 'resume'), default='activate')
    parser.add_argument('--instructions', default='')
    parser.add_argument('--user-requested', action='store_true')
    args = parser.parse_args()
    if args.action == 'activate':
        result = activate(args.vault, current_instructions=args.instructions)
    else:
        result = change_capture('paused' if args.action == 'pause' else 'active', args.vault,
                                user_requested=args.user_requested, skill_active=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] in ('ready', 'recall_only', 'updated', 'unchanged') else 1


if __name__ == '__main__':
    raise SystemExit(main())
