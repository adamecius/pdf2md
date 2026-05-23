# Placeholder

This fixture directory exists so the schema_failure test can point at a real
raw output path. The schema_failed classification is exercised by a custom
connector function that returns PageExtractionIR-like data which fails
PageExtractionIR.model_validate; the real connector path on this fixture
would itself produce structurally valid PageExtractionIR.
