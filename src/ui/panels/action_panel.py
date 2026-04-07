from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class ActionPanel(QWidget):
    actions_changed = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.unit_costs = {"energy": 5.0, "water": 6.0, "food": 4.0, "fuel": 3.0, "materials": 4.0}
        self.available_budget = 200.0
        self.policy_cost = 0.0

        self.prompt_label = QLabel(
            "Step 1: Read the problem\n"
            "Step 2: Choose emergency supplies\n"
            "Step 3: Run the turn"
        )
        self.prompt_label.setWordWrap(True)

        self.energy_input = self._make_spinbox()
        self.water_input = self._make_spinbox()
        self.food_input = self._make_spinbox()
        self.fuel_input = self._make_spinbox()
        self.materials_input = self._make_spinbox()

        self.energy_help = QLabel("Cost: $5 per unit\nHelps reduce power shortage risk.")
        self.water_help = QLabel("Cost: $6 per unit\nHelps protect water service.")
        self.food_help = QLabel("Cost: $4 per unit\nHelps protect food supply.")
        self.fuel_help = QLabel("Cost: $3 per unit\nHelps power generation keep running.")
        self.materials_help = QLabel("Cost: $4 per unit\nHelps repairs and reduces system losses.")
        for label in [self.energy_help, self.water_help, self.food_help, self.fuel_help, self.materials_help]:
            label.setWordWrap(True)

        self.energy_cost_label = QLabel("Current purchase: 0 units = $0")
        self.water_cost_label = QLabel("Current purchase: 0 units = $0")
        self.food_cost_label = QLabel("Current purchase: 0 units = $0")
        self.fuel_cost_label = QLabel("Current purchase: 0 units = $0")
        self.materials_cost_label = QLabel("Current purchase: 0 units = $0")

        self.priority_label = QLabel("Choose a Service Priority")
        self.priority_input = QComboBox()

        self.policy_label = QLabel("Choose a Policy")
        self.policy_input = QComboBox()
        self.policy_help = QLabel("Select a policy to add one-turn relief or long-term support.")
        self.policy_help.setWordWrap(True)
        self.policy_cost_label = QLabel("Policy cost: $0")

        self.total_cost_label = QLabel("Emergency supply spend: $0")
        self.policy_budget_label = QLabel("Policy spend from town budget: $0")
        self.remaining_budget_label = QLabel("Emergency supply budget left: $200")
        self.submit_button = QPushButton("Run Turn")

        layout.addWidget(QLabel("Your Choices"))
        layout.addWidget(self.prompt_label)
        layout.addWidget(QLabel("Buy Emergency Energy"))
        layout.addWidget(self.energy_input)
        layout.addWidget(self.energy_help)
        layout.addWidget(self.energy_cost_label)
        layout.addWidget(QLabel("Buy Emergency Water"))
        layout.addWidget(self.water_input)
        layout.addWidget(self.water_help)
        layout.addWidget(self.water_cost_label)
        layout.addWidget(QLabel("Buy Emergency Food"))
        layout.addWidget(self.food_input)
        layout.addWidget(self.food_help)
        layout.addWidget(self.food_cost_label)
        layout.addWidget(QLabel("Buy Emergency Fuel"))
        layout.addWidget(self.fuel_input)
        layout.addWidget(self.fuel_help)
        layout.addWidget(self.fuel_cost_label)
        layout.addWidget(QLabel("Buy Emergency Materials"))
        layout.addWidget(self.materials_input)
        layout.addWidget(self.materials_help)
        layout.addWidget(self.materials_cost_label)
        layout.addWidget(self.priority_label)
        layout.addWidget(self.priority_input)
        layout.addWidget(self.policy_label)
        layout.addWidget(self.policy_input)
        layout.addWidget(self.policy_help)
        layout.addWidget(self.policy_cost_label)
        layout.addWidget(self.total_cost_label)
        layout.addWidget(self.policy_budget_label)
        layout.addWidget(self.remaining_budget_label)
        layout.addWidget(self.submit_button)
        layout.addStretch(1)

        self.priority_input.addItem("Balance Services", "balance_services")
        self.priority_input.addItem("Keep Water Running", "keep_water_running")
        self.priority_input.addItem("Protect Food Supply", "protect_food_supply")
        self.priority_input.addItem("Stabilize Power", "stabilize_power")

        for widget in [self.energy_input, self.water_input, self.food_input, self.fuel_input, self.materials_input]:
            widget.valueChanged.connect(self._update_cost_summary)
            widget.valueChanged.connect(lambda *_: self.actions_changed.emit())
        self.priority_input.currentIndexChanged.connect(lambda *_: self.actions_changed.emit())
        self.policy_input.currentIndexChanged.connect(self._update_cost_summary)
        self.policy_input.currentIndexChanged.connect(lambda *_: self.actions_changed.emit())
        self._update_cost_summary()

    def _make_spinbox(self):
        spinbox = QSpinBox()
        spinbox.setRange(0, 40)
        spinbox.setSingleStep(5)
        return spinbox

    def set_context(self, unit_costs, available_budget):
        self.unit_costs = dict(unit_costs)
        self.available_budget = float(available_budget)
        self.energy_help.setText(
            f"Cost: ${self.unit_costs['energy']:.0f} per unit\nHelps reduce power shortage risk."
        )
        self.water_help.setText(
            f"Cost: ${self.unit_costs['water']:.0f} per unit\nHelps protect water service."
        )
        self.food_help.setText(
            f"Cost: ${self.unit_costs['food']:.0f} per unit\nHelps protect food supply."
        )
        self.fuel_help.setText(
            f"Cost: ${self.unit_costs['fuel']:.0f} per unit\nHelps power generation keep running."
        )
        self.materials_help.setText(
            f"Cost: ${self.unit_costs['materials']:.0f} per unit\nHelps repairs and reduces system losses."
        )
        self._update_cost_summary()

    def set_policy_options(self, policies):
        current_data = self.policy_input.currentData()
        current_policy_id = current_data["policy_id"] if current_data else None
        self.policy_input.blockSignals(True)
        self.policy_input.clear()
        self.policy_input.addItem("No policy this turn", None)
        for policy in policies:
            self.policy_input.addItem(policy["title"], policy)
        if current_policy_id:
            for index in range(self.policy_input.count()):
                data = self.policy_input.itemData(index)
                if data and data["policy_id"] == current_policy_id:
                    self.policy_input.setCurrentIndex(index)
                    break
        self.policy_input.blockSignals(False)
        self._update_cost_summary()

    def selected_policy(self):
        return self.policy_input.currentData()

    def _update_cost_summary(self):
        energy_total = self.energy_input.value() * self.unit_costs["energy"]
        water_total = self.water_input.value() * self.unit_costs["water"]
        food_total = self.food_input.value() * self.unit_costs["food"]
        fuel_total = self.fuel_input.value() * self.unit_costs["fuel"]
        materials_total = self.materials_input.value() * self.unit_costs["materials"]
        selected_policy = self.selected_policy()
        self.policy_cost = float(selected_policy["cost"]) if selected_policy else 0.0
        emergency_total = energy_total + water_total + food_total + fuel_total + materials_total
        remaining = self.available_budget - emergency_total
        self.energy_cost_label.setText(
            f"Current purchase: {self.energy_input.value()} units = ${energy_total:.0f}"
        )
        self.water_cost_label.setText(
            f"Current purchase: {self.water_input.value()} units = ${water_total:.0f}"
        )
        self.food_cost_label.setText(
            f"Current purchase: {self.food_input.value()} units = ${food_total:.0f}"
        )
        self.fuel_cost_label.setText(
            f"Current purchase: {self.fuel_input.value()} units = ${fuel_total:.0f}"
        )
        self.materials_cost_label.setText(
            f"Current purchase: {self.materials_input.value()} units = ${materials_total:.0f}"
        )
        if selected_policy:
            self.policy_help.setText(selected_policy["summary"])
            self.policy_cost_label.setText(f"Policy cost: ${self.policy_cost:.0f}")
        else:
            self.policy_help.setText("Select a policy to add one-turn relief or long-term support.")
            self.policy_cost_label.setText("Policy cost: $0")
        self.total_cost_label.setText(f"Emergency supply spend: ${emergency_total:.0f}")
        self.policy_budget_label.setText(f"Policy spend from town budget: ${self.policy_cost:.0f}")
        self.remaining_budget_label.setText(f"Emergency supply budget left: ${remaining:.0f}")

    def get_actions(self):
        return {
            "energy": float(self.energy_input.value()),
            "water": float(self.water_input.value()),
            "food": float(self.food_input.value()),
            "fuel": float(self.fuel_input.value()),
            "materials": float(self.materials_input.value()),
            "allocation_priority": self.priority_input.currentData(),
            "policy_id": self.selected_policy()["policy_id"] if self.selected_policy() else None,
        }

    def reset_inputs(self):
        for widget in [self.energy_input, self.water_input, self.food_input, self.fuel_input, self.materials_input]:
            widget.blockSignals(True)
            widget.setValue(0)
            widget.blockSignals(False)
        self.priority_input.blockSignals(True)
        self.priority_input.setCurrentIndex(0)
        self.priority_input.blockSignals(False)
        self.policy_input.blockSignals(True)
        self.policy_input.setCurrentIndex(0)
        self.policy_input.blockSignals(False)
        self._update_cost_summary()
        self.actions_changed.emit()
