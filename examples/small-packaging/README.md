# Factory C — Small Packaging Demo

A minimal **one Gateway, one Perspective project** example that users can copy as a directory structure.

| Item | Value |
| --- | --- |
| Factory | `lab-packaging` |
| Gateway | `packaging-main` |
| Project | `PackagingLineHMI` |
| View | `com.inductiveautomation.perspective/views/Main/view.json` |
| Source tag list | NOT PROVIDED |
| PLC/OPC UA live connection | NOT PROVIDED |
| EAM Agent | NOT COMMISSIONED |
| FAT | NOT TESTED |
| Allowed | Validate source / build ZIP only |

```bash
python framework/cli/validate_factory.py --factory lab-packaging --gateway packaging-main --project PackagingLineHMI --sha "$(git rev-parse HEAD)"
```

The Main view labels itself **DEMO ONLY — NO PLC/OPC UA/LIVE SIGNALS**. This project is a structural example, not a functional industrial automation system. It must not be automatically staged to the warehouse TEST Controller or a real production Gateway.
