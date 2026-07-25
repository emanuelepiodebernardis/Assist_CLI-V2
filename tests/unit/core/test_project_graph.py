from assist.core.project_graph import ProjectGraphBuilder


def test_project_graph_builds_import_relations(tmp_path):
    root = tmp_path / "project"
    root.mkdir()

    package_dir = root / "app"
    package_dir.mkdir()

    main_file = package_dir / "main.py"
    utils_file = package_dir / "utils.py"

    utils_file.write_text(
        "def helper():\n    return 1\n",
        encoding="utf-8",
    )

    main_file.write_text(
        "from app.utils import helper\n\nprint(helper())\n",
        encoding="utf-8",
    )

    builder = ProjectGraphBuilder()
    graph = builder.build(str(root))

    assert graph.root.endswith("project")
    assert len(graph.files) == 2

    main_node = next(node for node in graph.files if node.module == "app.main")
    utils_node = next(node for node in graph.files if node.module == "app.utils")

    assert "app.utils" in main_node.imports
    assert "app.main" in utils_node.imported_by