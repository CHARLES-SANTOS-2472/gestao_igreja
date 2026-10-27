(() => {
  const searchField = document.getElementById("id_occupation_search");
  const codeField = document.getElementById("id_occupation_code");
  const suggestions = document.getElementById("occupation-suggestions");
  const status = document.getElementById("occupation-status");
  const otherProfession = document.getElementById("id_profession");
  const script = document.currentScript;

  if (!searchField || !codeField || !suggestions || !status || !script) return;

  const searchUrl = script.dataset.searchUrl;
  if (!searchUrl) return;

  let timer;
  let controller;
  let requestNumber = 0;

  const setStatus = (message, isError = false) => {
    status.textContent = message;
    status.classList.toggle("is-error", isError);
  };

  const closeSuggestions = () => {
    suggestions.replaceChildren();
    suggestions.hidden = true;
  };

  const selectOccupation = (occupation) => {
    searchField.value = `${occupation.code} — ${occupation.title}`;
    codeField.value = occupation.code;
    if (otherProfession) otherProfession.value = "";
    closeSuggestions();
    setStatus(`Profissão selecionada: CBO ${occupation.code}.`);
  };

  const showResults = (occupations) => {
    suggestions.replaceChildren();
    if (occupations.length === 0) {
      suggestions.hidden = true;
      setStatus("Nenhuma ocupação encontrada. Você pode preencher outra profissão abaixo.");
      return;
    }

    for (const occupation of occupations) {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "occupation-option";
      option.setAttribute("role", "option");

      const code = document.createElement("span");
      code.className = "occupation-option-code";
      code.textContent = occupation.code;

      const title = document.createElement("span");
      title.className = "occupation-option-title";
      title.textContent = occupation.title;

      option.append(code, title);
      option.addEventListener("click", () => selectOccupation(occupation));
      suggestions.append(option);
    }

    suggestions.hidden = false;
    setStatus(`${occupations.length} opção(ões) encontrada(s).`);
  };

  searchField.addEventListener("input", () => {
    clearTimeout(timer);
    requestNumber += 1;
    controller?.abort();
    codeField.value = "";
    closeSuggestions();

    const query = searchField.value.trim();
    if (query.length < 2) {
      setStatus("Digite pelo menos 2 caracteres para pesquisar no catálogo CBO.");
      return;
    }

    const currentRequest = requestNumber;
    timer = window.setTimeout(async () => {
      controller = new AbortController();
      setStatus("Pesquisando ocupações CBO...");
      try {
        const url = new URL(searchUrl, window.location.origin);
        url.searchParams.set("q", query);
        const response = await fetch(url, {
          headers: { Accept: "application/json" },
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("A pesquisa CBO não respondeu.");
        const data = await response.json();
        if (currentRequest !== requestNumber) return;
        showResults(data.results);
      } catch (error) {
        if (error.name === "AbortError" || currentRequest !== requestNumber) return;
        closeSuggestions();
        setStatus("Não foi possível pesquisar a CBO. Tente novamente.", true);
      }
    }, 250);
  });

  searchField.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSuggestions();
    if (event.key === "ArrowDown" && !suggestions.hidden) {
      event.preventDefault();
      suggestions.querySelector("button")?.focus();
    }
  });

  suggestions.addEventListener("keydown", (event) => {
    const options = Array.from(suggestions.querySelectorAll("button"));
    const currentIndex = options.indexOf(document.activeElement);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      options[Math.min(currentIndex + 1, options.length - 1)]?.focus();
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (currentIndex <= 0) searchField.focus();
      else options[currentIndex - 1]?.focus();
    }
    if (event.key === "Escape") {
      closeSuggestions();
      searchField.focus();
    }
  });

  document.addEventListener("click", (event) => {
    if (!suggestions.contains(event.target) && event.target !== searchField) {
      closeSuggestions();
    }
  });

  searchField.addEventListener("change", () => {
    if (!codeField.value) searchField.value = "";
  });

  otherProfession?.addEventListener("input", () => {
    if (!otherProfession.value.trim()) return;
    codeField.value = "";
    searchField.value = "";
    closeSuggestions();
    setStatus("Profissão fora da CBO informada.");
  });
})();
