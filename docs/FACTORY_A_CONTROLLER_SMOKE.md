# Factory A isolated Controller smoke

Source is a new project named FactoryASmoke, not WarehouseHMI. On a dedicated TEST lab runner, the adapter backs up Controller and Agent project trees before mutation, creates the new project on the EAM Controller only, compares file SHA256 and requests an authenticated Controller project scan. It never executes EAM Send Project, does not affect the Agent and does not prove browser rendering or FAT. Production is out of scope. The workflow on the development branch triggers this stage only once when its own YAML file is first pushed.
