### Changed

- The plan audit judges an infrastructure plan's isolation, scoping, and least-privilege claims only against the resources the plan's own code creates. A resource the toolchain or platform creates, such as a deployment tool's bootstrap roles, is informational when the plan names it in a closed exception list with a reason; an unlisted toolchain resource is still audited (BACKLOG #487).
