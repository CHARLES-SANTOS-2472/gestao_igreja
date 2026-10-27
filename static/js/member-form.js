(() => {
  const form = document.querySelector(".form-panel");
  if (!form) return;

  for (const root of form.querySelectorAll("[data-repeatable-select]")) {
    const original = root.querySelector("select[multiple]");
    const rows = root.querySelector("[data-select-rows]");
    const addButton = root.querySelector("[data-add-select]");
    if (!original || !rows || !addButton) continue;

    const selectedValues = Array.from(original.selectedOptions)
      .map((option) => option.value)
      .filter(Boolean);
    const fieldName = original.name;
    const fieldLabel = root.closest(".family-field")?.querySelector("label")?.textContent.trim()
      || fieldName;
    const label = root.closest(".family-field")?.querySelector("label");
    const originalId = original.id;
    let nextId = 0;

    const noneOption = document.createElement("option");
    noneOption.value = "";
    noneOption.textContent = "Nenhum";
    original.insertBefore(noneOption, original.firstChild);

    const updateAvailableOptions = () => {
      const chosen = new Set(
        Array.from(rows.querySelectorAll("select"))
          .map((select) => select.value)
          .filter(Boolean),
      );
      for (const select of rows.querySelectorAll("select")) {
        for (const option of select.options) {
          option.disabled = Boolean(option.value)
            && option.value !== select.value
            && chosen.has(option.value);
        }
      }
      const selections = rows.querySelectorAll(".family-select-row");
      for (const row of selections) {
        const removeButton = row.querySelector("[data-remove-select]");
        if (removeButton) removeButton.disabled = selections.length === 1;
      }
    };

    const addRow = (selectedValue = "") => {
      const row = document.createElement("div");
      row.className = "family-select-row";

      const select = original.cloneNode(true);
      select.multiple = false;
      select.removeAttribute("multiple");
      select.removeAttribute("size");
      select.hidden = false;
      select.disabled = false;
      select.name = fieldName;
      select.id = `${originalId}-${nextId}`;
      select.setAttribute("aria-label", `${fieldLabel}, seleção ${nextId + 1}`);
      nextId += 1;

      for (const option of select.options) {
        option.selected = option.value === selectedValue;
      }

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "button button-quiet remove-family-select";
      removeButton.textContent = "Remover";
      removeButton.setAttribute("aria-label", `Remover ${fieldLabel.toLowerCase()}`);
      removeButton.dataset.removeSelect = "";
      removeButton.addEventListener("click", () => {
        row.remove();
        if (!rows.querySelector("select")) addRow();
        updateAvailableOptions();
      });

      select.addEventListener("change", updateAvailableOptions);
      row.append(select, removeButton);
      rows.append(row);
      if (nextId === 1 && label) label.htmlFor = select.id;
      updateAvailableOptions();
      return select;
    };

    original.hidden = true;
    original.disabled = true;
    original.id = `${originalId}-template`;
    for (const value of selectedValues) addRow(value);
    if (selectedValues.length === 0) addRow();
    addButton.addEventListener("click", () => addRow().focus());
  }

  const dateInputs = form.querySelectorAll(
    "#id_birth_date, #id_joined_on, #id_baptized_on, #id_deceased_on",
  );
  for (const input of dateInputs) {
    input.addEventListener("input", () => {
      const digits = input.value.replace(/\D/g, "").slice(0, 8);
      input.value = digits.length > 4
        ? `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`
        : digits.length > 2
          ? `${digits.slice(0, 2)}/${digits.slice(2)}`
          : digits;
    });
  }
})();
