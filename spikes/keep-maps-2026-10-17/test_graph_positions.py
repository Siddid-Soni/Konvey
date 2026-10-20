"""A graph keeps the node positions it first had, across beats and scenes (render.keep_maps)."""

import re

from konvey.render import keep_maps
from konvey.stage.displays.graph.positions import keep_positions


def nodes(page: str) -> list[str]:
    return re.findall(r'<graph[^>]* nodes="([^"]*)"', page)


def test_a_later_scene_with_other_coordinates_gets_the_first_map():
    s1 = '<graph id="map" nodes="A:0,0;B:2,2;C:2,-1" edges="A-B;A-C">'
    s3 = '<graph id="map" nodes="A:0,0;C:2,1.5;B:4,0" edges="A-B;A-C" path="A-C">'
    out = keep_positions([s1, s3])
    assert out[0] == s1
    assert nodes(out[1]) == ["A:0,0;C:2,-1;B:2,2"]        # same towns, same places
    assert 'path="A-C"' in out[1]


def test_names_only_take_the_positions_given_before():
    s1 = '<graph id="g" nodes="A:0,0;B:3,2;C:3,-2" edges="A-B">'
    s2 = '<graph id="g" nodes="A,B,C" edges="A-B">'
    assert nodes(keep_positions([s1, s2])[1]) == ["A:0,0;B:3,2;C:3,-2"]


def test_a_node_added_later_lands_where_that_scene_put_it_relative_to_the_others():
    s1 = '<graph id="g" nodes="A:0,0;B:2,0" edges="A-B">'
    # drawn twice as big and shifted: D sits above the middle of A-B
    s2 = '<graph id="g" nodes="A:10,10;B:14,10;D:12,14" edges="A-B;B-D">'
    assert nodes(keep_positions([s1, s2])[1]) == ["A:0,0;B:2,0;D:1,2"]


def test_other_graphs_and_row_layouts_are_left_alone():
    s1 = '<graph id="g" nodes="A:0,0;B:2,0"><graph id="w" nodes="the,cat" layout="line">'
    s2 = '<graph id="h" nodes="A:5,5;B:0,0"><graph id="w" nodes="the,cat,sat" layout="line">'
    assert keep_positions([s1, s2]) == [s1, s2]


def test_keep_maps_rewrites_the_scene_pages_in_scene_order(tmp_path):
    (tmp_path / "agent3-S1.html").write_text('<graph id="g" nodes="A:0,0;B:1,0">')
    (tmp_path / "agent3-S2.html").write_text('<graph id="g" nodes="A:0,0;B:0,1">')
    (tmp_path / "agent3-S2.tagged.html").write_text('<graph id="g" nodes="A:0,0;B:0,1">')
    keep_maps(tmp_path)
    assert nodes((tmp_path / "agent3-S2.html").read_text()) == ["A:0,0;B:1,0"]
    assert nodes((tmp_path / "agent3-S2.tagged.html").read_text()) == ["A:0,0;B:0,1"]
