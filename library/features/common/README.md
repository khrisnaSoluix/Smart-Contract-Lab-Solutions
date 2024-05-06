Any modules inside `library.features.common` must be agnostic to the Contract API major version.
To determine if this is the case, consider whether any the following applies:

- The function uses Vault-specific Contract API types. Even if these have the same name or are
functionally equivalent, they are imported from different sources (`contracts_api` for v4 and
`types` for v3) and therefore not interchangeable
- The function uses native python Contract API types at a module level in v3 that now requires
specific method imports in v4 (e.g. `calendar.is_leap` in v3 vs `is_leap` in v4)
- The function uses native python Contract API types that have been renamed and aren't
interchangeable (e.g `json_dumps` in v3 versus `dumps()` in v4)
- The function uses third party python Contract API types that have been renamed and aren't
interchangeable (e.g `timedelta` in v3 versus `dateutil.relativedelta` in v4, or
`parse_to_datetime` vs `dateutil.parse`)

In order to avoid renderer namespace clashes, modules within this directory must be suffixed with
`_common`. Any template using a feature defined in `library.features.common` should do so via a
similarly named feature inside `library.features.v3` or `library.features.v4` and would be prone to
clashes. For example, if `library.features.v3.my_feature` imports
`library.features.common.my_feature`, the renderer will namespace both as `my_feature`, causing
problems if there are objects within either have the same name.
