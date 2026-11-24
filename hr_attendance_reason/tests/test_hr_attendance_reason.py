# Copyright 2017 Odoo S.A.
# Copyright 2018 ForgeFlow, S.L.
# Copyright 2023 Tecnativa - Víctor Martínez
# License LGPL-3 - See http://www.gnu.org/licenses/lgpl-3.0.html

from datetime import datetime

from odoo.tests import new_test_user, users
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DF

from odoo.addons.base.tests.common import BaseCommon


class TestHrAttendanceReason(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.att_reason_model = cls.env["hr.attendance.reason"]
        cls.user = new_test_user(
            cls.env,
            login="test-user",
            groups="base.group_user,hr_attendance.group_hr_attendance_own_reader",
        )
        cls.employee = cls.env["hr.employee"].create(
            {"name": cls.user.login, "user_id": cls.user.id}
        )
        cls.att_reason_in = cls.att_reason_model.create(
            {"name": "Bus did not come", "code": "BB", "action_type": "sign_in"}
        )
        cls.att_reason_out = cls.att_reason_model.create(
            {"name": "A lot of work", "code": "WORK", "action_type": "sign_out"}
        )

    @users("test-user")
    def test_employee_edit(self):
        self.env["hr.attendance"].sudo().create(
            {
                "employee_id": self.env.user.employee_id.id,
                "check_in": datetime.now().strftime(DF),
                "attendance_reason_ids": [(4, self.att_reason_in.id)],
            }
        )
        # check out
        attendance = self.env.user.employee_id.with_context(
            attendance_reason_id=self.att_reason_out.id
        )._attendance_action_change({})
        self.assertIn(self.att_reason_in, attendance.attendance_reason_ids)
        self.assertIn(self.att_reason_out, attendance.attendance_reason_ids)

    @users("test-user")
    def test_user_attendance_manual(self):
        # check in
        attendance = self.env.user.employee_id.with_context(
            attendance_reason_id=self.att_reason_in.id
        )._attendance_action_change({})
        self.assertIn(self.att_reason_in, attendance.attendance_reason_ids)
        # check out
        attendance = self.env.user.employee_id.with_context(
            attendance_reason_id=self.att_reason_out.id
        )._attendance_action_change({})
        self.assertIn(self.att_reason_out, attendance.attendance_reason_ids)

    def test_department_default_sign_out(self):
        """Test that department default is applied when employee has a department."""
        # Create department with default sign-out reason
        department = self.env["hr.department"].create(
            {
                "name": "Test Department",
                "default_sign_out_reason_id": self.att_reason_out.id,
            }
        )
        # Create employee with department
        employee = self.env["hr.employee"].create(
            {"name": "Test Employee", "department_id": department.id}
        )
        # Check in first
        self.env["hr.attendance"].sudo().create(
            {
                "employee_id": employee.id,
                "check_in": datetime.now().strftime(DF),
            }
        )
        # Check out without context reason - should use department default
        attendance = employee.sudo()._attendance_action_change({})
        self.assertIn(self.att_reason_out, attendance.attendance_reason_ids)

    def test_fallback_to_company_default(self):
        """Test that company default is used when department has no defaults."""
        # Create department without defaults
        department = self.env["hr.department"].create({"name": "Empty Department"})
        # Set company defaults
        company = self.env.company
        company.write(
            {
                "reason_on_attendance_screen_default_sign_in": self.att_reason_in.id,
                "reason_on_attendance_screen_default_sign_out": self.att_reason_out.id,
            }
        )
        # Create employee in department
        employee = self.env["hr.employee"].create(
            {"name": "Test Employee 2", "department_id": department.id}
        )
        # Check in first
        self.env["hr.attendance"].sudo().create(
            {
                "employee_id": employee.id,
                "check_in": datetime.now().strftime(DF),
            }
        )
        # Check out - should use company default
        attendance = employee.sudo()._attendance_action_change({})
        self.assertIn(self.att_reason_out, attendance.attendance_reason_ids)

    def test_isolation_between_departments(self):
        """Test that changing one department's default doesn't affect others."""
        # Create two departments with different defaults
        reason_out_1 = self.att_reason_model.create(
            {"name": "Dept1 Reason", "code": "D1", "action_type": "sign_out"}
        )
        reason_out_2 = self.att_reason_model.create(
            {"name": "Dept2 Reason", "code": "D2", "action_type": "sign_out"}
        )
        department1 = self.env["hr.department"].create(
            {
                "name": "Department 1",
                "default_sign_out_reason_id": reason_out_1.id,
            }
        )
        department2 = self.env["hr.department"].create(
            {
                "name": "Department 2",
                "default_sign_out_reason_id": reason_out_2.id,
            }
        )
        # Create employees in each department
        employee1 = self.env["hr.employee"].create(
            {"name": "Employee 1", "department_id": department1.id}
        )
        employee2 = self.env["hr.employee"].create(
            {"name": "Employee 2", "department_id": department2.id}
        )
        # Check in both employees
        self.env["hr.attendance"].sudo().create(
            {
                "employee_id": employee1.id,
                "check_in": datetime.now().strftime(DF),
            }
        )
        self.env["hr.attendance"].sudo().create(
            {
                "employee_id": employee2.id,
                "check_in": datetime.now().strftime(DF),
            }
        )
        # Check out employee1 - should use department1's default
        attendance1 = employee1.sudo()._attendance_action_change({})
        self.assertIn(reason_out_1, attendance1.attendance_reason_ids)
        self.assertNotIn(reason_out_2, attendance1.attendance_reason_ids)
        # Check out employee2 - should use department2's default
        attendance2 = employee2.sudo()._attendance_action_change({})
        self.assertIn(reason_out_2, attendance2.attendance_reason_ids)
        self.assertNotIn(reason_out_1, attendance2.attendance_reason_ids)
