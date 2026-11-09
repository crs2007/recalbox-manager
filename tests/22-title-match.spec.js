const { test, expect } = require('./fixtures');
const { execFileSync } = require('child_process');
const path = require('path');

const root = path.resolve(__dirname, '..');

test('wiki search hits must actually match the game', () => {
  const code = String.raw`
import sys, json
sys.path.insert(0, ${JSON.stringify(root)})
import server as s
p = s._pick_matching_title
print(json.dumps({
  "related_page": p("Super Mario Bros.", ["Mario", "Super Mario Bros. Z (film)"]),
  "exact": p("Super Mario Bros.", ["Mario", "Super Mario Bros. (video game)"]),
  "character": p("Sonic the Hedgehog", ["Sonic the Hedgehog (character)", "Sonic Boom"]),
  "game_over_char": p("Sonic the Hedgehog", ["Sonic the Hedgehog (character)", "Sonic the Hedgehog (1991)"]),
  "the_order": p("Legend of Zelda, The (USA)", ["The Legend of Zelda"]),
  "nothing": p("Aladdin", []),
  "bootleg_systems": sorted([x for x in s.SCRAPE_SOURCES if x["name"] == "Bootleg Games Wiki"][0]["systems"]),
}))
`;
  const out = JSON.parse(execFileSync('python', ['-c', code], { encoding: 'utf8' }).trim().split('\n').pop());
  expect(out.related_page).toBeNull();
  expect(out.exact).toBe('Super Mario Bros. (video game)');
  expect(out.character).toBeNull();
  expect(out.game_over_char).toBe('Sonic the Hedgehog (1991)');
  expect(out.the_order).toBe('The Legend of Zelda');
  expect(out.nothing).toBeNull();
  expect(out.bootleg_systems).toEqual(['famicom', 'gb', 'gbc', 'megadrive', 'nes', 'snes']);
});
