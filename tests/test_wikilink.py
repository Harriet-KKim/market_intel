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


def test_inject_wikilinks_word_boundary(sample_registry_dir):
    """L4: alias가 다른 단어의 substring에 매칭되지 않아야 한다.

    예: keyword alias "humanoid"가 "superhumanoidal" 내부에 매칭되면 안 되고,
    company alias "Isaac"이 "Isaacson" 내부에 매칭되면 안 된다.
    """
    from src.registry import Registry
    from src.writer.wikilink import inject_wikilinks

    registry = Registry(sample_registry_dir)

    # "humanoid" alias가 "superhumanoidal" 내부를 오염시키면 안 된다.
    text1 = "The word superhumanoidal is not a humanoid reference."
    result1 = inject_wikilinks(text1, registry)
    assert "[[Humanoid Robot]]" in result1, "standalone 'humanoid' should match"
    assert "super[[Humanoid Robot]]al" not in result1, "substring inside 'superhumanoidal' should not match"
    assert "superhumanoidal" in result1, "superhumanoidal should remain unchanged"

    # "Isaac" alias (NVIDIA)가 "Isaacson" 내부를 오염시키면 안 된다.
    text2 = "Isaacson wrote about Isaac Sim usage."
    result2 = inject_wikilinks(text2, registry)
    assert "[[NVIDIA]] Sim" in result2, "standalone 'Isaac' should match"
    assert "Isaacson" in result2, "Isaacson should remain unchanged"
    assert "[[NVIDIA]]son" not in result2


def test_inject_wikilinks_korean_alias_with_boundary(sample_registry_dir):
    """L4: 한글 alias는 한글-ASCII 경계에서 올바르게 매칭된다."""
    from src.registry import Registry
    from src.writer.wikilink import inject_wikilinks

    registry = Registry(sample_registry_dir)
    text = "엔비디아 칩이 새로 발표됐다."
    result = inject_wikilinks(text, registry)
    assert "[[NVIDIA]]" in result
