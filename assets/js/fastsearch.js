import * as params from '@params';

let fuse;
let resList = document.getElementById('searchResults');
let sInput = document.getElementById('searchInput');
let first, last, current_elem = null;
let resultsAvailable = false;
let debounceTimer = null;

const MIN_CHARS = (params.fuseOpts && params.fuseOpts.minmatchcharlength) || 3;
const DEBOUNCE_MS = 200;

window.onload = function () {
    let xhr = new XMLHttpRequest();
    xhr.onreadystatechange = function () {
        if (xhr.readyState === 4) {
            if (xhr.status === 200) {
                let data = JSON.parse(xhr.responseText);
                if (data) {
                    let options = {
                        distance: 100,
                        threshold: 0.4,
                        ignoreLocation: true,
                        includeScore: true,
                        keys: ['title', 'summary', 'content']
                    };
                    if (params.fuseOpts) {
                        options = {
                            isCaseSensitive: params.fuseOpts.iscasesensitive ?? false,
                            includeScore: true,
                            includeMatches: params.fuseOpts.includematches ?? false,
                            minMatchCharLength: params.fuseOpts.minmatchcharlength ?? 1,
                            shouldSort: params.fuseOpts.shouldsort ?? true,
                            findAllMatches: params.fuseOpts.findallmatches ?? false,
                            keys: params.fuseOpts.keys ?? ['title', 'summary', 'content'],
                            location: params.fuseOpts.location ?? 0,
                            threshold: params.fuseOpts.threshold ?? 0.4,
                            distance: params.fuseOpts.distance ?? 100,
                            ignoreLocation: params.fuseOpts.ignorelocation ?? true
                        };
                    }
                    fuse = new Fuse(data, options);
                    document.dispatchEvent(new CustomEvent('fuseReady'));
                }
            } else {
                console.log(xhr.responseText);
            }
        }
    };
    xhr.open('GET', "../index.json");
    xhr.send();
};

function parseQuery(raw) {
    const phrases = [];
    const stripped = raw.replace(/"([^"]+)"/g, (_, p) => {
        phrases.push(p.trim().toLowerCase());
        return '';
    });
    const terms = stripped.split(/\s+/).filter(t => t.length >= 2).map(t => t.toLowerCase());
    const fuseQuery = raw.replace(/"/g, '').trim();
    return { phrases, terms, fuseQuery };
}

function postFilter(results, phrases, terms) {
    return results.filter(r => {
        const hay = (r.item.title + ' ' + (r.item.summary || '') + ' ' + r.item.content).toLowerCase();
        for (const p of phrases) {
            if (!hay.includes(p)) return false;
        }
        for (const t of terms) {
            if (!hay.includes(t)) return false;
        }
        return true;
    });
}

function escapeRegex(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function highlight(text, phrases, terms) {
    const parts = phrases.map(escapeRegex).concat(terms.map(escapeRegex)).filter(Boolean);
    if (parts.length === 0) return text;
    const re = new RegExp('(' + parts.join('|') + ')', 'gi');
    return text.replace(re, '<mark>$1</mark>');
}

function makeSnippet(content, phrases, terms, maxLen) {
    maxLen = maxLen || 200;
    const lower = content.toLowerCase();
    const allTerms = phrases.concat(terms);
    let bestPos = 0;
    for (const t of allTerms) {
        const idx = lower.indexOf(t);
        if (idx !== -1) {
            bestPos = Math.max(0, idx - 40);
            break;
        }
    }
    let snippet = content.substring(bestPos, bestPos + maxLen);
    if (bestPos > 0) snippet = '\u2026' + snippet;
    if (bestPos + maxLen < content.length) snippet += '\u2026';
    return highlight(snippet, phrases, terms);
}

function activeToggle(ae) {
    document.querySelectorAll('.focus').forEach(function (element) {
        element.classList.remove("focus");
    });
    if (ae) {
        ae.focus();
        document.activeElement = current_elem = ae;
        ae.parentElement.classList.add("focus");
    } else {
        document.activeElement.parentElement.classList.add("focus");
    }
}

function reset() {
    resultsAvailable = false;
    resList.innerHTML = sInput.value = '';
    sInput.focus();
}

function executeSearch(query) {
    if (!fuse) return;

    if (query.replace(/"/g, '').trim().length < MIN_CHARS) {
        resultsAvailable = false;
        if (query.length > 0) {
            resList.innerHTML = '<li class="search-no-results">Type at least ' + MIN_CHARS + ' characters to search</li>';
        } else {
            resList.innerHTML = '';
        }
        return;
    }

    const { phrases, terms, fuseQuery } = parseQuery(query);

    let results;
    const limit = (params.fuseOpts && params.fuseOpts.limit) || 100;
    results = fuse.search(fuseQuery, { limit });

    let filtered = postFilter(results, phrases, terms);

    if (filtered.length === 0) {
        resultsAvailable = false;
        resList.innerHTML = '<li class="search-no-results">No results found.</li>';
        return;
    }

    const seen = new Set();
    const unique = filtered.filter(r => {
        if (seen.has(r.item.permalink)) return false;
        seen.add(r.item.permalink);
        return true;
    });

    unique.sort((a, b) => {
        const scoreDiff = (a.score || 0) - (b.score || 0);
        if (Math.abs(scoreDiff) > 0.01) return scoreDiff;
        return (b.item.date || '').localeCompare(a.item.date || '');
    });

    let resultSet = '';
    for (let item of unique) {
        const coverHtml = item.item.cover
            ? `<img src="${item.item.cover}" class="search-result-cover" alt="" loading="lazy">`
            : `<div class="search-result-cover search-result-cover-placeholder"></div>`;
        const dateHtml = item.item.date
            ? `<p class="search-entry-date">${item.item.date}</p>`
            : '';
        const titleHtml = highlight(item.item.title, phrases, terms);
        const snippetHtml = makeSnippet(item.item.content || '', phrases, terms);
        resultSet +=
            `<li class="post-entry search-entry">` +
            coverHtml +
            `<div class="search-entry-text">` +
            `<header class="entry-header">${titleHtml}&nbsp;»</header>` +
            dateHtml +
            `<p class="search-entry-snippet">${snippetHtml}</p>` +
            `</div>` +
            `<a href="${item.item.permalink}" aria-label="${item.item.title}"></a>` +
            `</li>`;
    }

    resList.innerHTML = resultSet;
    resultsAvailable = true;
    first = resList.firstChild;
    last = resList.lastChild;
}

sInput.onkeyup = function (e) {
    const query = this.value.trim();
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => executeSearch(query), DEBOUNCE_MS);
};

sInput.addEventListener('search', function (e) {
    if (!this.value) reset();
});

document.onkeydown = function (e) {
    let key = e.key;
    let ae = document.activeElement;
    let inbox = document.getElementById("searchbox").contains(ae);

    if (ae === sInput) {
        let elements = document.getElementsByClassName('focus');
        while (elements.length > 0) {
            elements[0].classList.remove('focus');
        }
    } else if (current_elem) ae = current_elem;

    if (key === "Escape") {
        reset();
    } else if (!resultsAvailable || !inbox) {
        return;
    } else if (key === "ArrowDown") {
        e.preventDefault();
        if (ae == sInput) {
            activeToggle(resList.firstChild.lastChild);
        } else if (ae.parentElement != last) {
            activeToggle(ae.parentElement.nextSibling.lastChild);
        }
    } else if (key === "ArrowUp") {
        e.preventDefault();
        if (ae.parentElement == first) {
            activeToggle(sInput);
        } else if (ae != sInput) {
            activeToggle(ae.parentElement.previousSibling.lastChild);
        }
    } else if (key === "ArrowRight") {
        ae.click();
    }
};
