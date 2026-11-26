# De-Nova for Firefox

Stylesheets that make Firefox's Nova redesign look like the old (pre-Nova) interface: squarer corners, neutral greys and a blue accent instead of violet tints, no violet-to-orange toolbar gradient, the old tab and settings layout, and the old icon drawings. Written against Firefox 161 on Windows.

Inspired by [JibsouX/firefox-proton-anti-nova-theme](https://github.com/JibsouX/firefox-proton-anti-nova-theme), a larger and more complete take on the same idea. This repo is independent: its icon mapping is generated from Firefox's own stylesheets, and no files are taken from that project.

| Path | What it is |
|---|---|
| `chrome/userChrome.css` | Styles the browser UI: tabs, toolbars, URL bar, bookmarks bar, menus and popups, sidebar. |
| `chrome/userContent.css` | Styles Firefox's own pages only (`about:` and `chrome:`), such as Settings, Add-ons and `about:config`. Websites are untouched. |
| `chrome/de-nova-icons.css`, `chrome/de-nova-icons-content.css`, `chrome/de-nova-icons/` | The old icon drawings (190 SVGs taken from Firefox's own files, MPL 2.0) and the rules that apply them in the browser UI and on Firefox's pages. Generated. |
| `user.js` | The three preferences the stylesheets need. |
| `tools/gen_icons.py` | Regenerates the icon files from the installed Firefox. |

## Install

1. Open `about:support` and click **Open Folder** next to *Profile Folder*.
2. Copy this repo's `chrome/` folder into the profile folder (merge with an existing `chrome/` folder after backing it up) and copy `user.js` next to it. If you already have a `user.js`, add its three lines to yours.
3. Restart Firefox.

To remove it, delete the files you copied and restart.

## What it changes

- Corner radii back to 2, 4 and 8px (URL bar, tabs, buttons, menus and popups, cards).
- Violet accent and tinted hover states replaced by Photon blue (cyan in dark mode) and plain translucent greys.
- No toolbar gradient and no coloured outline around the selected tab.
- Tab strip back to 36px tabs with 4px above and below; container-tab line flush inside the top edge of the tab and full width.
- Toolbar icons 2px larger, button size unchanged.
- Settings and Add-ons side navigation back to the square pale highlight with a blue bar, softer icon grey, and dropdowns without Nova's outline.
- Add-ons and similar message bars back to the tinted background with the centred round icon.
- White (not grey-tinted) page backgrounds on Firefox's own pages.
- The old icon drawings in the browser UI and on Firefox's own pages.

Toolbar and URL-field colours are only set when no theme is active, so an installed theme keeps control of them.

## Adjust

Each setting is a CSS custom property or a short rule in `userChrome.css`:

- `--icon-grow` (toolbar icons): each `1px` adds `2px` to the icon; `0px` is the original size.
- `--tab-context-line-outer-offset`: vertical position of the container-tab line; raise it to move the line down.
- `--tab-context-line-inline-offset`: inset of the container-tab line from the tab edges; `0px` is full width.
- `--tab-min-height` and `--tab-margin-block`: tab height and the space above and below the tabs.

## How the icons work

Firefox ships each Nova-aware icon as one SVG holding both the old (`proton`) and new (`nova`) drawing, switched by a rule inside the file that stylesheets cannot reach. `tools/gen_icons.py`:

1. writes a copy of each such SVG with only the old drawing, and
2. reads Firefox's own skin stylesheets and replays every rule that gives an element an icon, with the same selector and conditions, pointing at the old-drawing copy where one exists. Rules are replayed, not just the ones that use two-drawing icons, so specificity and order between competing rules stay as Firefox has them (otherwise a generic icon rule would override a more specific one, such as the Firefox logo on `about:` pages).

Rules that would not be safe in a user stylesheet are left out: stylesheets Firefox loads only inside web-component shadow roots (their bare selectors, such as `toolbarbutton`, are scoped to the component there and would otherwise match every toolbar button), and rules that target a bare `body` or `html` (page-specific sheets). The script prints the sheets it skipped.

Run it after a Firefox update that changes icons; the instructions are at the top of the script. Icons that Firefox sets from script, or draws through properties other than `list-style-image`, `background-image`, `mask-image`, `content` and custom properties, are not covered.

## Limits

- Firefox themes cannot carry CSS, so this cannot be packaged as a theme. It needs these files in the profile.
- Firefox components that define their own tokens (for example `moz-select`, `moz-message-bar` and the settings side navigation) ignore values set on the page root, so each needs a rule on the component itself. Any component not covered keeps its Nova look.
- Mozilla has marked the `browser.nova.enabled` pref for removal. Once it is gone Nova can no longer be switched off, and values here may need adjusting to whatever replaces it. The icon generator also depends on the old drawings still being present in Firefox's SVGs.

## Licence

The stylesheets and script are MIT licensed (`LICENSE`). The SVGs in `chrome/de-nova-icons/` come from Firefox and remain under the Mozilla Public License 2.0; each file keeps its header.
