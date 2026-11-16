# AeroPulse AI update

## Demo workflow improvements
- Routine warning toasts and map tile warning overlays are no longer shown. Emergency alerts remain enabled.
- No-fly zones and incidents can be configured before the demo.
- The Run demo action preserves the operator's prepared setup rather than resetting zones/incidents.
- Emergency Generator supports pre-generating a batch of 1–50 incidents.
- New random incidents are generated outside no-fly zones; manually specified locations inside restricted zones are rejected.
- Incidents covered by a newly added/edited no-fly zone are marked EXCLUDED.
- At completion of each drone's inspection sweep, all remaining pending incidents in its assigned region are detected, except those inside no-fly zones.
- Incident history and map distinguish excluded incidents.

## Verification
- Python compilation passed.
- 5 automated tests passed.
- Frontend JSX syntax transpilation passed.
- API smoke test confirmed preconfigured zones/incidents survive Run demo.
