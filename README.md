# mySociety Developer Information

This site holds information for mySociety developers and volunteers, to help
them produce better code, open better issues, and create pull requests more
likely to be accepted.

## This Site

### Compiling

This site is mostly compiled by magic (specifically
[Jekyll](http://jekyllrb.com/) and [Compass](http://compass-style.org/), using
the [Foundation](http://foundation.zurb.com/) framework), which will have to be
installed before you can do anything. The following commands will install the
necessary software:

* `sudo gem install github-pages` for preference, or (if you have an older
  version of Ruby) `sudo gem install jekyll`
* `sudo gem install zurb-foundation`
* `sudo gem install compass`

You may find the following commands useful:

* `jekyll serve --watch` - Starts a web server on `localhost:4000` with the
  latest compiled copy of the site. Recompiles when files change.
* `compass watch` - Monitors static asset folders (most usefully the `sass`
  folder) for changes, and recompiles when necessary.

### Workflow

Since this site involves describing standards, changes should be properly
controlled and discussed. This should be done through GitHub pull requests.

#### Substantial Changes

To propose substantial changes, such as a change in an actual standard, here's
what to do:

1. Branch `master`, giving your new branch a sensible name.
2. Open a GitHub pull request from your feature branch to `master`. This is
   where debating the merits of changes should happen.
3. When everybody is happy with the changes, merge the branch into `master`.
   The pull request on GitHub will close itself, and the published site will
   recompile.

#### Minor Changes

If you are making a minor, uncontentious change (such as updating a list of
references or fixing a typo) then changes can be made directly on the `master`
branch. The published site will recompile once changes are pushed to GitHub.
