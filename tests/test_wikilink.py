def test_inject_wikilinks(sample_registry_dir):
    from src.registry import Registry
    from src.writer.wikilink import inject_wikilinks

    registry = Registry(sample_registry_dir)
    text = "NVIDIA announced a partnership with Figure AI on humanoid robots."

    result = inject_wikilinks(text, registry)

    assert "[[NVIDIA]]" in result
    assert "[[Figure AI]]" in result


def test_inject_wikilinks_no_double_wrap(sample_registry_dir):
    from src.registry import Registry
    from src.writer.wikilink import inject_wikilinks

    registry = Registry(sample_registry_dir)
    text = "[[NVIDIA]] already has wikilinks."

    result = inject_wikilinks(text, registry)

    assert result.count("[[NVIDIA]]") == 1
    assert "[[[[NVIDIA]]]]" not in result
