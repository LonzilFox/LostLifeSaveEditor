# Save format and field interpretation

## Verified from two local user-provided samples

- The SharedObject name is `HLB02_Core_1.52`.
- The file starts with the `00 BF` Flash SOL header and `TCSO` signature.
- The payload is AMF3 (`3`).
- Both samples contain 59 top-level keys.
- Sample A contains 150 traversed nodes / 132 primitive or directly editable values.
- Sample B contains 151 traversed nodes / 133 primitive or directly editable values.
- One additional nested key appears in sample B. New keys are discovered dynamically.
- Both samples include objects and indexed arrays.

A change between two saves is a **correlation**, not proof that the field controls a particular mechanic. Values such as 999 or 99999 do not establish valid upper limits.

## Field groups

1. Progress and dates
2. Heart-related values and display modes
3. Internal character state
4. Statistical counters
5. Appearance and color selection
6. Internal content/state flags
7. Audio
8. Graphics and performance
9. Input and interaction
10. Language and system
11. Unknown future fields

`field_manifest.json` lists every observed nested field path and its type, without including the player's values.

## Serialization

The writer regenerates valid AMF3 values and the SOL byte length, then parses the resulting bytes to verify that every value survives. Strings and traits are emitted inline; object references are emitted when necessary. The editor also reparses the file after atomic replacement.

Supported AMF3 values include integer, double, Boolean, string, null, object, array, date, XML, ByteArray, vector and dictionary (where applicable). Externalizable objects require game-specific handling and are rejected.
